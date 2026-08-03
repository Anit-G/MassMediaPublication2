from __future__ import annotations
import os
import json
import time
import subprocess
import shlex
import random

try:
    import cv2
except ImportError:
    cv2 = None

try:
    import scipy
except ImportError:
    scipy = None

try:
    import ffmpeg as ff
except ImportError:
    ff = None

try:
    import numpy as np
except ImportError:
    class DummyNP:
        ndarray = object
    np = DummyNP()

try:
    import soundfile as sf
except ImportError:
    sf = None

try:
    from pydub import AudioSegment
except ImportError:
    AudioSegment = None

import Utils.Central_Logger as log
import Utils.Config_vars as config
from Utils.DB_Operations import DBOps, Status, signature, write_path
from typing import Optional
        
class VideoGen:
    def __init__(self):
        # initialize the SQLite DB
        log.INFO(f"Initialized Video Generator: ")
        self._voice_map = config.KOKORO_VOICEMAP
        self._dbops = DBOps(config.METADB_PATH)
    
    def _load_templates(self, path: str = config.TEMPLATES_PATH) -> dict:
        with open(path, 'r') as f:
            return json.load(f)   
        
    def _image_to_video(self, ebook_no):
        cmd = f'''ffmpeg -y -loop 1 -i "{config.BGP_FOLDER+f"/book_{ebook_no}.jpg"}" \
            -f lavfi -t {config.VIDEO_DURATION} -i anullsrc=r=48000:cl=stereo \
            -shortest -c:v h264_nvenc -preset fast -r {config.FPS} \
            -c:a aac -b:a 192k -pix_fmt yuv420p -t {config.VIDEO_DURATION} "{config.BGV_FOLDER+f"/book_{ebook_no}.mp4"}"'''
        subprocess.run(shlex.split(cmd), check=True)
    
    def _check_thumbnail(self, ebook_no: int):
        # Check if thumbnail exists, if not generate via Image Generation using Gemini
        if not os.path.exists(config.BGP_FOLDER+f"/book_{ebook_no}.jpg"):
            log.ERROR(f"VideoGen[{ebook_no}]: Missing Video Thumbnail as configured in template ABORTING!!!")
            return False
        # Check if thumbnail MP4 Exists, if not generate via ffmpeg looping the thumbnail
        if not os.path.exists(config.BGV_FOLDER+f"/book_{ebook_no}.mp4"):
            self._image_to_video(ebook_no)
        return True
    
    def _build_template(self, ebook_no: int, category: str) -> dict:
        assert self._check_thumbnail(ebook_no)
        
        standard_template = self._load_templates()
        book_info = self._dbops.get_book_author(ebook_no)
        if not book_info:
            log.ERROR(f"VideoGen[{ebook_no}]: Missing ebook number")
            return dict()
                
        template_dict = {}
        template_dict["BGM"] = random.choice(standard_template[category])
        template_dict["BGP"] = f"book_{ebook_no}.jpg"
        template_dict["thumbnail"] = f"book_{ebook_no}.jpg" # Needs to be created manually
        template_dict["tags"] = [book_info[0]]
        
        template_dict["use_BGV"] = config.USE_STILL_BGV
        if config.USE_STILL_BGV:
            # This is the thumbnail looped into a MP4
            template_dict["BGV"] = f"book_{ebook_no}.mp4"
        else:
            template_dict["BGV"] = random.choice(standard_template["available_BGVs"])
        if config.USE_STILL_FOR_SHORTS:
            # This is the thumbnail looped into a MP4 for shorts aspect ratio
            template_dict["short"] = f"book_{ebook_no}.mp4"
        else:
            template_dict["short"] = random.choice(standard_template["available_BGV_Shortform"])
        
        # Dump the standard_template
        standard_template[f"book_{ebook_no}"] = template_dict
        with open(config.TEMPLATES_PATH,'w') as f:
            json.dump(standard_template, f, indent=4)
        
        return template_dict
    
    def _get_resolution(self, file_path: str) -> list:
        res = [config.VIDEO_RESOLUTION[0],config.VIDEO_RESOLUTION[1]]
        try:
            cmd = [
                'ffprobe',
                '-v', 'error',
                '-select_streams', 'v:0',
                '-show_entries', 'stream=width,height',
                '-of', 'json',
                file_path
            ]
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            metadata = json.loads(result.stdout)
            
            width = metadata['streams'][0]['width']
            height = metadata['streams'][0]['height']
            res = [width, height]
        except Exception as e:
            log.ERROR(f"Error getting background resolution: {e}")
        return res
      
    def _generate_video(self,
                  dialog_pth: str,
                  bg_music_pth: str,
                  bg_file_pth: str,
                  output_file_pth: str,
                  signature: str) -> None:    
        # Get resolution based on background file
        bg_resolution = [config.VIDEO_RESOLUTION[0],config.VIDEO_RESOLUTION[1]]
        log.INFO(f"VideoGen[{signature}]: Generating video in resolution: {bg_resolution[0]}x{bg_resolution[1]}")
        
        # Check if directory exists:
        if not os.path.exists(os.path.dirname(output_file_pth)): 
            os.mkdir(os.path.dirname(output_file_pth))       
        
        # Visuals
        if bg_file_pth.split(".")[-1].lower() == "mp4":
            background_video = ff.input(bg_file_pth)
        else:
            log.ERROR(f"background file given is not an accepted format of video: {bg_file_pth}")
            return
        
        # video_out = background_video
        main_video = background_video.video
        
        # Audio
        params = {'I': -15.0, 'TP': -2.0, 'LRA': 7.0}
        dialog_audio = ff.input(dialog_pth).audio.filter('loudnorm', **params)
        # dialog_audio = dialog_audio.filter('adelay', delays='5000|5000').filter('aresample')
        background_music = ff.input(bg_music_pth).audio.filter('volume', volume=config.BGM_VOLUME)

        main_audio = ff.filter([dialog_audio, background_music], 'amix', inputs=2, duration='first')

        # write to filesystem
        try:
            (ff
                .output(main_video, main_audio, output_file_pth, # type: ignore
                        vcodec='h264_nvenc', acodec='aac', r=config.FPS, shortest=None,
                        pix_fmt='yuv420p', movflags='+faststart', preset='fast')
                .overwrite_output()
                .run(quiet=False)
            )
        except Exception as e:
            log.ERROR(f"Exception was raised during ffmpeg operation to generate final video: {e}")
        log.INFO(f"VideoGen[{signature}]: generated {output_file_pth}")  
    
    def video_compiler(self, book: list, use_short: bool, category: str) -> None:
        """ 
        For each book we extract the signature and relative path of the audio to generate a video
        The generation is done per audio ie per chapter given incase shorts audio is available generation is done for the same.

        Args:
            book (list): it contains the ebook_no, chapter index, voice code, chapter header and relative path of the chapter audio file.
                It needs to be sourced from CHAPTER_PROGRESS table
            use_short (bool): booleaan to control the generation of shorts whether the audio files exist or not, 
                if true all available audios are used to generate a video short and update DB in SHORTS_PROGRESS.
        """
        ebook_no = book[0]
        section_no = book[1]
        voice_code = book[2]
        rel_path = book[4]

        template = self._load_templates().get("book_"+str(ebook_no))
        if template is None:
            log.ERROR(f"Template doesn't exist: book_{ebook_no}")
            # Create Template:
            template = self._build_template(ebook_no, category)

        start = time.time()
        dialog_pth = rel_path
        bg_music_pth = config.BGM_FOLDER + "/" + template["BGM"]
        bg_file_pth = config.BGV_FOLDER + "/" + template["BGV"]
        output_file_pth = write_path(ebook_no, voice_code, section_no, Status.PossibleStates.VIDEO_GEN)
        
        if not os.path.exists(output_file_pth):

            self._generate_video(dialog_pth, bg_music_pth, bg_file_pth, output_file_pth, signature(ebook_no, voice_code, section_no))
            end = time.time()
            elapsed_str = f"{end-start:.2f}"
            log.INFO(f"Time taken to generate Main Video for book {ebook_no} section {section_no} voice \"{self._voice_map[voice_code]}\": Time {elapsed_str}")
        else:
            log.INFO(f"Main Video for book {ebook_no} section {section_no} voice \"{self._voice_map[voice_code]}\" at {output_file_pth} is already GENERATED")
            
        if use_short:
            start = time.time()
            shorts_audio_paths = self._dbops.can_start_shorts_video_gen(ebook_no, voice_code, section_no)
            if shorts_audio_paths == []:
                return None
            
            for idx, audio_path in shorts_audio_paths:
                self._dbops.update_shorts_status(ebook_no, voice_code, section_no, idx, Status.PossibleStates.VIDEO_GEN, Status.ChapterStatus.GENERATING)
                # if shorts background file is a video then its in the BGV folder else it is in the BGP folder 
                bg_file_pth = config.BGV_FOLDER + "/" + template["short"]
                short_output_file_pth = write_path(ebook_no, voice_code, section_no, Status.PossibleStates.VIDEO_GEN, shorts_idx=idx)  
                          
                self._generate_video(audio_path, bg_music_pth, bg_file_pth, short_output_file_pth, signature(ebook_no, voice_code, section_no))
                
                # update db for shorts status
                self._dbops.update_shorts_status(ebook_no, voice_code, section_no, idx, Status.PossibleStates.VIDEO_GEN, Status.ChapterStatus.COMPLETED)
            end = time.time()
            short_elapsed_str = f"{end-start:.2f}"
            log.INFO(f"Time taken to generate Shorts for book {ebook_no} section {section_no} voice \"{self._voice_map[voice_code]}\": Time {short_elapsed_str}")

    def generate_chapter_video(self, category: str, use_short: bool = False) -> bool:
        """
        Generate a single chapter video from a provided audio path.
        """
        res = self._dbops.get_next_action_category(category, Status.ProcessingStage.PROCESSING, Status.PossibleStates.VIDEO_GEN)
        if res is None:
            return False
        
        ebook_no, chapter_idx = res
        voice_codes = self._dbops.get_voice_codes(category)
        
        if voice_codes is None:
            return False
        
        for voice_code in voice_codes:
            audio_path = self._dbops.can_start_video_gen(ebook_no, voice_code, chapter_idx)
            if audio_path is None:
                return False
            
            self._dbops.update_chapter_status(ebook_no, voice_code, chapter_idx, Status.PossibleStates.VIDEO_GEN, Status.ChapterStatus.GENERATING)
                
            if not audio_path:
                log.ERROR(f"VideoGen[{ebook_no}]: Missing audio path for ebook {ebook_no} section {chapter_idx}")
                return False

            if not os.path.exists(audio_path):
                log.ERROR(f"VideoGen[{ebook_no}]: Audio file not found at {audio_path} for ebook {ebook_no} section {chapter_idx}")
                return False
            try:
                book_record = [ebook_no, chapter_idx, voice_code, "", audio_path]
                self.video_compiler(book_record, use_short=use_short, category=category)
                self._dbops.update_chapter_status(ebook_no, voice_code, chapter_idx, Status.PossibleStates.VIDEO_GEN, Status.ChapterStatus.COMPLETED)
            except Exception as exc:
                log.ERROR(f"VideoGen[{ebook_no}]: failed to generate video for ebook {ebook_no}, section {chapter_idx}, voice {voice_code}: {exc}")
                self._dbops.mark_chapter_retry(ebook_no, voice_code, chapter_idx, 
                    Status.PossibleStates.VIDEO_GEN, str(exc), 
                    base_delay=config.RETRY_BASE_DELAY_SECONDS,
                    backoff_factor=config.RETRY_BACKOFF_FACTOR,
                    max_retries=config.RETRY_MAX_ATTEMPTS,) 
        return True
    
    def generate_chapter_video_retries(self) -> None:
        video_chapter_list = self._dbops.get_stage_retries(Status.PossibleStates.VIDEO_GEN)
        for ebook_no, voice_code, chapter_idx, category in video_chapter_list:
            try:
                log.INFO(f"VideoGen[{ebook_no}:{voice_code}:{chapter_idx}]: begin retries")
                self._dbops.update_chapter_status(ebook_no, voice_code, chapter_idx, Status.PossibleStates.VIDEO_GEN, Status.ChapterStatus.GENERATING)
                audio_path = config.AUD_FILEPATH + f"/Book_{ebook_no}/{str(ebook_no).zfill(5)}_{str(voice_code).zfill(2)}_{str(chapter_idx).zfill(3)}_chapsection.wav"
                book_record = [ebook_no, chapter_idx, voice_code, "", audio_path]
                self.video_compiler(book_record, use_short=False, category=category)
                self._dbops.update_chapter_status(ebook_no, voice_code, chapter_idx, Status.PossibleStates.VIDEO_GEN, Status.ChapterStatus.COMPLETED)
            except Exception as exc:
                log.ERROR(f"VideoGen[{ebook_no}:{voice_code}:{chapter_idx}]: failed to generate video retry: {exc}")
                self._dbops.mark_chapter_retry(ebook_no, voice_code, chapter_idx, 
                    Status.PossibleStates.VIDEO_GEN, str(exc), 
                    base_delay=config.RETRY_BASE_DELAY_SECONDS,
                    backoff_factor=config.RETRY_BACKOFF_FACTOR,
                    max_retries=config.RETRY_MAX_ATTEMPTS,) 