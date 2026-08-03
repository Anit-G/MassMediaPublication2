from __future__ import annotations
import time
import os
import json
import re
from typing import Union, List, Optional, Any

try:
    import numpy as np
except ImportError:
    class DummyNP:
        ndarray = Any
    np = DummyNP()

try:
    import soundfile as sf
except ImportError:
    sf = None

import Utils.Config_vars as config
import Utils.Central_Logger as log

try:
    from kokoro import KPipeline
except ImportError:
    KPipeline = None

from Utils.DB_Operations import DBOps, Status, signature, write_path
from typing import Union, List, Optional, Any

try:
    from .WeightedKPipeline import WeightedKPipeline
except ImportError:
    WeightedKPipeline = None

class TTS:
    def __init__(self, dist_weight: float = 0.5, mixer: int = 7):
        self._VOICE_MAP_ENG = config.KOKORO_VOICEMAP
        self.dist_weight = dist_weight
        self.mixer = mixer
        self._dbops = DBOps(config.METADB_PATH)
        self._pipelines = dict()
        if WeightedKPipeline is not None:
            for _, code in self._VOICE_MAP_ENG.items():
                if(code[0] not in self._pipelines.keys()):
                    try:
                        pipeline = WeightedKPipeline(lang_code=code[0], device='cpu', repo_id='hexgrad/Kokoro-82M')
                        self._pipelines[code[0]] = pipeline
                    except Exception as e:
                        log.ERROR(f"Failed to initialize WeightedKPipeline for {code[0]}: {e}")
        else:
            log.INFO("WeightedKPipeline not available, running in mock/demo mode")
        
        log.INFO(f"Number of pipelines created: {len(self._pipelines)}")
        if not os.path.exists(config.AUD_FILEPATH):
            os.makedirs(config.AUD_FILEPATH)
        if not os.path.exists(config.SUM_FILEPATH):
            os.makedirs(config.SUM_FILEPATH)
            
    def get_books_content(self, category: str) -> Union[tuple[dict,int,int], None]:
        result = self._dbops.get_next_action_category(category, Status.ProcessingStage.PROCESSING, Status.PossibleStates.AUDIO_GEN)
        if not result:
            log.ERROR(f"TTS: No book found for category {category}, skipping TTS generation.")
            return None
        ebook_no, chapter_idx = result
        
        # TODO: need to add shorts info in DB as well.
        
        log.INFO(f"TTS [{ebook_no}]: Load book chapter {chapter_idx} for category {category}")
        book_content = self._load_book_content(ebook_no)
        
        if book_content:
            return (book_content, ebook_no, chapter_idx)
        
        log.WARNING(f"TTS[{ebook_no}]: Returning none book content")
        return None
        
    
    def _clean_text(self, text: List[str]) -> List[str]:
        # clean the content
        clean_text = []
        for c in text:
            c = re.sub(r"\[.*?\]|\{.*?\}", " ", c)
            c = c.replace('\r', ' ').replace('\n', ' ').replace('(','.').replace(')','.').replace('!', '.').replace('?', '.').replace(';', '.').replace(':', '.').replace('...', '.')
            c = re.sub(r'[^A-Za-z0-9 ,\-!\'"“”‘’.]+', '', c)
            c = re.sub(r'\s{2,}', ' ', c)
            c = c.strip()
            c = c.replace(',', '.').replace('.', '...')
            if c != " " and c != "":
                clean_text.append(c)            
        return clean_text
        
    def _convert_chapter(self, chapter: dict) -> Union[tuple[List[str], List[str]], tuple[None, None]]:
        # tHe function accepts individual chapters ONLY
        if 'content' in chapter.keys():
            content = chapter['content']
        else:
            log.ERROR("Incorrect chapter format")
            return None, None

        header = ["\n".join([chapter[x] for x in chapter.keys() if x != 'content'])]

        return content, header

    def _load_book_content(self, ebook_no: int) -> Union[dict, None]:
        filepath = f"{config.JSON_FILEPATH}/book_{ebook_no}.json"
        if not os.path.exists(filepath):
            log.ERROR(f"TTS [{ebook_no}]: Book JSON missing at {filepath}")
            return None

        with open(filepath, 'r', encoding="utf-8") as file:
            data = json.load(file)

        if data is None or 'Book_Content' not in data:
            log.ERROR(f"TTS [{ebook_no}]: Invalid book JSON or missing Book_Content at {filepath}")
            return None
        
        log.INFO(f"TTS [{ebook_no}]: Book JSON content loaded")
        return data['Book_Content']

    def _generate_chapter_audio(
        self,
        ebook_no: int,
        voice_code: int,
        chapter_idx: int,
        category: str,
        content: List[str],
        full_header: List[str],
        generate_header: bool = True,
        generate_chapter: bool = True
    ) -> tuple[Union[str, None], Union[str, None]]:

        chapter_path = write_path(ebook_no, voice_code, chapter_idx, Status.PossibleStates.AUDIO_GEN)
        head_path = write_path(ebook_no, voice_code, chapter_idx, Status.PossibleStates.AUDIO_GEN, headsectionFlag = True)

        if not os.path.exists(os.path.dirname(head_path)):
            os.makedirs(os.path.dirname(head_path), exist_ok=True)

        if generate_header:
            head_tmp = head_path + ".tmp"
            head_aud = self._generate_audio_kokoro(voice_code, self._clean_text(full_header), category)
            if sf is not None and hasattr(head_aud, 'shape'):
                sf.write(head_tmp, head_aud, config.AUD_SAMPLE_RATE)
            else:
                # Mock or fallback write
                with open(head_tmp, "wb") as f:
                    f.write(b"RIFF_MOCK_HEADER_AUDIO")
            os.replace(head_tmp, head_path)
        else:
            head_path = None

        if generate_chapter:
            ch_tmp = chapter_path + ".tmp"
            ch_aud = self._generate_audio_kokoro(voice_code, self._clean_text(content), category)
            if sf is not None and hasattr(ch_aud, 'shape'):
                sf.write(ch_tmp, ch_aud, config.AUD_SAMPLE_RATE)
            else:
                # Mock or fallback write
                with open(ch_tmp, "wb") as f:
                    f.write(b"RIFF_MOCK_CHAPTER_AUDIO")
            os.replace(ch_tmp, chapter_path)
        else:
            chapter_path = None
            
        return head_path, chapter_path

    def _generate_chapter_shorts_audio(
        self,
        ebook_no: int,
        voice_code: int,
        chapter_idx: int,
        category: str,
        content: List[str], 
    ) -> list[str]:

        lines = self._clean_text(" ".join(content).split("."))
        len_per_line = [len(s.split()) for s in lines]
        no_words = sum(len_per_line)
        average_wpm = config.AVERAGE_SHORTS_WPM
        words_per_short = int((config.SHORTS_LENGTH_MINUTES * average_wpm) * config.SHORTS_LENGTH_CORRECTION_FACTOR)
        if words_per_short <= 0:
            words_per_short = max(1, no_words)

        # Create batches of lines for shorts based on words_per_short
        curr_batch_len = 0
        batches = []
        batch_lines = []
        for idx, ll in enumerate(len_per_line):
            if curr_batch_len + ll <= words_per_short:
                curr_batch_len += ll
                batch_lines.append(lines[idx])
            elif ll >= words_per_short:
                curr_batch_len = 0
                batches.append(batch_lines)
                batches.append(lines[idx].strip())
                batch_lines = []
            else:
                batches.append(batch_lines)
                batch_lines = [lines[idx].strip()]
                curr_batch_len = ll
        if batch_lines:
            batches.append(batch_lines)

        audio_paths = []
        log.INFO(f"TTS[{ebook_no}:{voice_code}:{chapter_idx}]: Number of shorts: {len(batches)}, MAX word per short: {words_per_short}")
        for short_id, batch in enumerate(batches):
            if not batch and short_id <= config.MAX_SHORTS_PER_CHAPTER:
                continue
            aud = self._generate_audio_kokoro(voice_code, batch, category)
            short_path = write_path(ebook_no, voice_code, chapter_idx, Status.PossibleStates.AUDIO_GEN, shorts_idx = short_id)
            sf.write(short_path, aud, config.AUD_SAMPLE_RATE)
            audio_paths.append(short_path)            
        return audio_paths

    def _generate_audio_kokoro(self, voice_code: Union[int, List[int]], text: Union[str, List[str]], category: str = "cat(WS)", model_speed: float = config.TTS_MODEL_SPEED) -> np.ndarray:
        if isinstance(voice_code, int):
            voices = self._VOICE_MAP_ENG[voice_code]
            pipeline = self._pipelines[voices[0]]
        else: 
            # support for multi voice averaging (Lang_code has to be the same for the voice)
            voices = self._VOICE_MAP_ENG[voice_code[0]]
            for vc in voice_code[1:]:
                voices = voices +","+ self._VOICE_MAP_ENG[vc]
            pipeline = self._pipelines[voices[0]]
             
        generator = pipeline(
            text,
            voices = voices,
            speed = model_speed,
            split_pattern = r'\n+',
            voice_dist = self.dist_weight
        )
        
        audio_chunks = []
        for _, (_, _, audio) in enumerate(generator):
            audio_chunks.append(audio)
            # add breaths
            breath_pth = os.path.join(config.BREATH_IN_PATH, f"pause.mp3")
            if os.path.exists(breath_pth):
                breath_data, _ = sf.read(breath_pth) # breath is stereo
                audio_chunks.append(breath_data[:,0])
            else:
                log.ERROR(f"Breath file not found at {breath_pth}")
        log.INFO(f"TTS Audio generated: {len(audio_chunks)}, {generator}, {len(audio_chunks)}")
            
        final_aud = np.concatenate(audio_chunks, axis = 0)
        if config.STEREO_AUD:
            # Convert mono to stereo by duplicating the channel
            stereo_audio = np.stack((final_aud, final_aud), axis=-1)  # Shape: (samples, 2)
            
            # add chimes
            if config.USE_CHIMES:
                chimes_pth = os.path.join(config.CHIME_PATH, f"{category[4:6]}.mp3")
                if os.path.exists(chimes_pth):
                    chime_data, _ = sf.read(chimes_pth)
                    if chime_data.shape[1] == 2:
                        stereo_audio = np.concatenate((chime_data, stereo_audio, chime_data), axis=0)
                    else:
                        log.ERROR(f"Chime file at {chimes_pth} is not stereo, skipping chime addition.")
                else:
                    log.ERROR(f"Chime file not found at {chimes_pth}")
            else:
                silence_pth = os.path.join(config.CHIME_PATH, "silence.mp3")
                if os.path.exists(silence_pth):
                    silence_data, _ = sf.read(silence_pth)
                    if silence_data.shape[1] == 2:
                        stereo_audio = np.concatenate((silence_data, stereo_audio), axis = 0)
                    else:
                        log.ERROR("Given silence is mono audio")
                else:
                    log.ERROR("Silence file Missing")
                
            return stereo_audio
        else:
            return final_aud
    
    def direct_tts_generation(self, **kwargs):
        text_sample = kwargs.get("text_sample", "I just wanted to say that I might sound a bit robotic but, I, am, doing, my, best... the, world, is, black, and, white, turned, to, color, only, at, your, sight,... You. my. love. are. my. soulmate. my. reason. to. live!!!")
        print("============================================== GENERATING SAMPLE FOR KOKORO ==============================================")
        for key, vc in self._VOICE_MAP_ENG.items():
            print(f"Generating sample for {vc}")
            text_sample = f"I, just, wanted, to, say, that, I, might, sound, a, bit, robotic, but, I, am, doing, my, best... the, world, is, black, and, white, turned, to, color, only, at, your, sight,... You, my, love, are, my, soulmate. my, reason, to, live!!!"
            aud = self._generate_audio_kokoro(key, text_sample)  
            # save the audio
            sample_dir = "./TTS/UnitTests/KoKoro_samples/"
            os.makedirs(sample_dir,exist_ok=True)
            sf.write(sample_dir+f"sample_{vc}_06.wav", aud, config.AUD_SAMPLE_RATE)
            print(f"Saving sample for {vc}\n\n")
        print("============================================== GENERATION FOR KOKORO IS COMPLETE ==============================================")
    
    def direct_tts_mixed_generation(self, keys, **kwargs):
        text_sample = kwargs.get("text_sample", "I just wanted to say that I might sound a bit robotic but, I, am, doing, my, best... the, world, is, black, and, white, turned, to, color, only, at, your, sight,... You. my. love. are. my. soulmate. my. reason. to. live!!!")
        print("============================================== GENERATING SAMPLE FOR KOKORO WITH Voice Mixing ==============================================")
        print(f"Generating sample for {keys}")
        aud = self._generate_audio_kokoro(keys, text_sample)  
        # save the audio
        sample_dir = "./TTS/UnitTests/KoKoro_samples/"
        os.makedirs(sample_dir,exist_ok=True)
        sf.write(sample_dir+f"mix_sample_{keys[0]}_{keys[1]}@{self.dist_weight}_07.wav", aud, config.AUD_SAMPLE_RATE)
        print(f"Saving sample for {keys}")
        print("============================================== GENERATION FOR KOKORO IS COMPLETE ==============================================")

    def _run_tts_all_chapters(self, book_content: dict, ebook_no: int, voice_code: int, category: str, use_short: bool = False):
        for ch_idx, ch_key in enumerate(book_content):
            chapter_content = book_content[ch_key].get('content')
            if  chapter_content is None:
                log.INFO(f"TTS [{ebook_no}]: empty {ch_key}, skip chapter")
                self._dbops.update_chapter_status(ebook_no, voice_code, ch_idx, Status.PossibleStates.AUDIO_GEN, Status.ChapterStatus.MANUAL_REVIEW_NEEDED)
                continue
            
            self._run_tts_single_chapter(chapter_content, ebook_no, voice_code, category, ch_idx, use_short)
                
    def _run_tts_single_chapter(self, chapter_content: dict, ebook_no: int, voice_code: int, category: str, ch_idx: int, use_short: bool = False):
        """ Run TTS for a single chapter given the chapter key, content and ebook number

        Args:
            chapter_content (dict): Content of the chapter
            ebook_no (int): ebook number as per Gutenberg project
            voice_code (int): Voice code for the TTS engine kokoro82M
            category (str): Category of the ebook
            ch_key (str): Key for the chapter as per Json structure is "Chapter_0", "Chapter_1", etc.
            ch_idx (int): 
                Index of the chapter as per iteration order, starts from 0 with increment of 1 for each chapter
                Regardless of the actual chapter number in the JSON file. So if the JSON has "Chapter_1", "Chapter_5", "Chapter_7", the ch_idx for 
                these will be 0, 1, 2 respectively when iterating through the JSON file in order. This is done to maintain the order of chapters as 
                per the JSON file and to have a consistent naming convention for the audio files. ch_idx is used for naming and DB storage so it is more
                important ch_key is used only for JSON parsing.
            use_short (bool, optional): Whether to generate shorts for the chapter. Defaults to False.

        Returns:
            None: None but functinally will generate audio files for the chapter and update DB accordingly.
        """

        if chapter_content.get('header') is None:
            log.INFO(f"TTS [{ch_idx}:{ebook_no}:{voice_code}]: chapter {ch_idx} has no header, using default header")
            chapter_content['header'] = f"Chapter_{ch_idx}"
            
        elif chapter_content.get('header', '').lower() in config.NON_TTS_CHAPTERS:
            log.INFO(f"TTS [{ch_idx}:{ebook_no}:{voice_code}]: skipping chapter, non tts chapter")
            self._dbops.update_chapter_status(ebook_no, voice_code, ch_idx, Status.PossibleStates.AUDIO_GEN, Status.ChapterStatus.MANUAL_REVIEW_NEEDED)
            return None

        if len(" ".join(chapter_content.get('content', []))) < config.MINIMUIM_CONTENT_LENGTH:
            log.INFO(f"TTS [{ch_idx}:{ebook_no}:{voice_code}]: skipping chapter, too small for a chapter")
            self._dbops.update_chapter_status(ebook_no, voice_code, ch_idx, Status.PossibleStates.AUDIO_GEN, Status.ChapterStatus.MANUAL_REVIEW_NEEDED)
            return None

        log.INFO(f"TTS[{ch_idx}:{ebook_no}:{voice_code}]: Audio generating for Chapter {ch_idx}")
        start = time.time()
        self._dbops.update_chapter_status(ebook_no, voice_code, ch_idx, Status.PossibleStates.AUDIO_GEN, Status.ChapterStatus.GENERATING)
        content = chapter_content.get('content')
        full_header = [chapter_content.get('header')]   

        try:
            head_path, chapter_path = self._generate_chapter_audio(
                ebook_no,
                voice_code,
                ch_idx,
                category,
                content, # type: ignore chapter content length is checked above
                full_header, # type: ignore chapter header is checked and defaulted above
                generate_header=True,
                generate_chapter=True
            )
        except Exception as exc:
            log.ERROR(f"TTS[{ch_idx}:{ebook_no}:{voice_code}]: Chapter audio generation failed, error: {exc}")
            self._dbops.mark_chapter_retry(ebook_no, voice_code, ch_idx, 
                    Status.PossibleStates.AUDIO_GEN, str(exc), 
                    base_delay=config.RETRY_BASE_DELAY_SECONDS,
                    backoff_factor=config.RETRY_BACKOFF_FACTOR,
                    max_retries=config.RETRY_MAX_ATTEMPTS,)  
            return None
                
        # Update DB only on successful generation
        self._dbops.update_chapter_status(ebook_no, voice_code, ch_idx, Status.PossibleStates.AUDIO_GEN, Status.ChapterStatus.COMPLETED)
    
        if use_short:
            short_paths = []
            try:
                short_paths = self._generate_chapter_shorts_audio(ebook_no, voice_code, ch_idx, category, content) # type: ignore chapter content length is checked above
                no_shorts = len(short_paths)
                no_words = sum(len(s.split()) for s in self._clean_text(content)) # type: ignore content length is checked above
            except Exception as exc:
                log.ERROR(f"TTS[{ch_idx}:{ebook_no}:{voice_code}]: Shorts audio generation failed, error {exc}")
                # TODO: DB update for failure for shorts
            
            # update DB with shorts info
            for short_id in range(len(short_paths)):
                self._dbops.update_shorts_status(ebook_no, voice_code, ch_idx, short_id, Status.PossibleStates.AUDIO_GEN, Status.ChapterStatus.COMPLETED)
        
        end = time.time()
        log.INFO(f"TTS[{ch_idx}:{ebook_no}:{voice_code}]: Runtime: {end-start:.2f} for Chapter idx: {ch_idx}")

    def generate_chapter_audio_for_worker(
        self,
        category: str,
        use_short: bool = False,
    ) -> None:
        
        voice_codes = self._dbops.get_voice_codes(category)
        if not voice_codes:
            log.ERROR(f"TTS: no voice codes found for category {category}")
            return None
        
        book_result = self.get_books_content(category)
        if not book_result:
            log.ERROR(f"TTS: Missing book content")
            return
        book_content, ebook_no, chapter_idx = book_result
        chapter_keys = list(book_content.keys())
        if chapter_idx < 0 or chapter_idx >= len(chapter_keys):
            # Chapter idx has a one to one mapping with chapter keys
            log.ERROR(f"TTS [{ebook_no}]: requested chapter_idx {chapter_idx} out of range")
            return

        chapter_key = chapter_keys[chapter_idx]
        chapter_content = book_content.get(chapter_key)
        if chapter_content is None:
            log.ERROR(f"TTS [{ebook_no}]: Chapter content for {chapter_key} is missing")
            return

        for voice_code in voice_codes:
            self._run_tts_single_chapter(
                chapter_content=chapter_content,
                ebook_no=ebook_no,
                voice_code=voice_code,
                category=category,
                ch_idx=chapter_idx,
                use_short=use_short,
            )
        
        return
    
    def generate_chapter_audio_retries(self) -> None:
        audio_chapter_list = self._dbops.get_stage_retries(Status.PossibleStates.AUDIO_GEN)
        for ebook_no, voice_code, chapter_idx, category in audio_chapter_list:
            # get book content
            book_content = self._load_book_content(ebook_no)
            if not book_content:
                log.ERROR(f"TTS Retries[{ebook_no}:{voice_code}:{chapter_idx}]: Failed to get book content")
                continue
            chapter_keys = list(book_content.keys())
            if chapter_idx < 0 or chapter_idx >= len(chapter_keys):
                log.ERROR(f"TTS Retries[{ebook_no}:{voice_code}:{chapter_idx}]: requested chapter_idx out of range")
                continue
            chapter_key = chapter_keys[chapter_idx]
            chapter_content = book_content.get(chapter_key)
            
            if chapter_content is None:
                log.ERROR(f"TTS Retries[{ebook_no}:{voice_code}:{chapter_idx}]: Chapter content for {chapter_key} is missing")
                continue
            
            self._run_tts_single_chapter(
                chapter_content=chapter_content,
                ebook_no=ebook_no,
                voice_code=voice_code,
                category=category,
                ch_idx=chapter_idx,
                use_short=False,
            ) 
        return
               
    def __call__(self, voice_codes: list, category: str, use_short: bool = False, single_generation: bool = False) -> None:
        """ TTS call function to generate audio for a given voice and category.

        Args:
            voice_codes (list): Voices of Kokoro82M integer mappings
            category (str): Each ebook is bucketed into 1 of 5 categories based on title and genre
            use_short (bool, optional): Whether to generate shorts for each chapter. Defaults to False.
            single_generation (bool, optional): Whether to generate audio per single chapter on function call or the entire book. Defaults to False.
        """
        # Voice codes are the indexs of _VOICE_MAP_ENG  
        try:
            book_result = self.get_books_content(category)
            if not book_result:
                return
            book_content, ebook_no, chapter_idx = book_result
            log.INFO(f"Running pipeline for voice codes: {voice_codes}, ebook: {ebook_no}, category: {category}")        
            
            if single_generation:
                # for testing and debugging purposes, run tts for only the first chapter and first voice code
                ch_key = list(book_content.keys())[chapter_idx]
                chapter_content = book_content.get(ch_key)
                if chapter_content is None:
                    log.ERROR(f"TTS [{ebook_no}]: Chapter content for chapter key {ch_key} is None, skipping TTS generation for this chapter.")
                    for voice_code in voice_codes:
                        self._dbops.update_chapter_status(ebook_no, voice_code, chapter_idx, Status.PossibleStates.AUDIO_GEN, Status.ChapterStatus.MANUAL_REVIEW_NEEDED)
                    return
                for voice_code in voice_codes:
                    self._run_tts_single_chapter(chapter_content, ebook_no, voice_code, category, chapter_idx, use_short)
            else:
                for voice_code in voice_codes:
                    self._run_tts_all_chapters(book_content, ebook_no, voice_code, category, use_short)
        except Exception as e:
            log.ERROR(f"TTS: Error occurred while running TTS for category {category}, voice codes {voice_codes}: {e}")
        