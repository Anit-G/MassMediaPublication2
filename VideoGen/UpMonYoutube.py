from __future__ import annotations
import os
import json, time

import Utils.Central_Logger as log
import Utils.Config_vars as config

from Utils.DB_Operations import DBOps, Status

try:
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.errors import HttpError
    HAS_GOOGLE_API = True
except ImportError:
    InstalledAppFlow = None
    build = None
    MediaFileUpload = None
    Credentials = None
    Request = None
    HttpError = Exception
    HAS_GOOGLE_API = False

class UpMonYouTube:
    def __init__(self, category: str):
        # Define the scopes
        self._dbops = DBOps()
        self.SCOPES = ["https://www.googleapis.com/auth/youtube.upload", "https://www.googleapis.com/auth/youtube.readonly", "https://www.googleapis.com/auth/youtube.force-ssl","https://www.googleapis.com/auth/youtube"]
        self.category = category
        self.voice_map = config.KOKORO_VOICEMAP
        self.MY_CHANNEL_ID = self._get_channel_id()
        self.API_CALL_COUNT = 0
        self.youtube_auth = None
        self._get_authenticated_service()
        log.INFO(f"INITIALIZING youtube monitoring and uploading class")

    def _get_channel_id(self):
        try:
            self._dbops._cursor.execute("SELECT yt_hash FROM YOUTUBE_MAP WHERE category = ?", (self.category,))
            res = self._dbops._cursor.fetchone()
            if res and res[0]:
                return res[0]
        except Exception as e:
            log.ERROR(f"Upload[{self.category}]: Error getting channel id: {e}")
        log.WARN(f"Upload[{self.category}]: Missing category in YOUTUBE_MAP table, using default hash")
        return "UC_default_hash"
    
    def _get_authenticated_service(self) -> None:
        if not HAS_GOOGLE_API:
            log.INFO("Google API packages not installed, YouTube service running in mock mode")
            self.youtube_auth = None
            return
        creds = None
        try:
            token = self._dbops.get_channel_token(self.MY_CHANNEL_ID)
            if token:
                creds = Credentials.from_authorized_user_info(token, self.SCOPES)

            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    try:
                        creds.refresh(Request())
                        self._dbops.set_channel_token(self.MY_CHANNEL_ID, creds.to_json())
                    except Exception as e:
                        log.ERROR(f"Token refresh failed: {e}")
                        creds = None

            if creds:
                self.youtube_auth = build("youtube", "v3", credentials=creds)
            else:
                self.youtube_auth = None
        except Exception as e:
            log.ERROR(f"Failed to authenticate YouTube service: {e}")
            self.youtube_auth = None

    def _upload_video_call(self, file_path: str, title: str, description: str, tags: list = [], privacy: str = "public", thumbnail_pth: str = "") -> str | None:
        body = {
            "snippet": {
                "title": title,
                "description": description,
                "tags": tags or [],
                "categoryId": "24"  # Category Id for entertainment
            },
            "status": {
                "privacyStatus": privacy
            }
        }

        try:
            media = MediaFileUpload(
                file_path,
                chunksize=-1,
                resumable=True
            )

            request = self.youtube_auth.videos().insert( # type: ignore
                part="snippet,status",
                body=body,
                media_body=media
            )
            response = None
            while response is None:
                status, response = request.next_chunk()
                if status:
                    log.INFO(f"Uploading… {int(status.progress() * 100)}%")
            log.INFO(f"Upload Request Sent, Video ID: {response['id']}")
            video_id = response["id"]
            
            upload_status_request = self.youtube_auth.videos().list( # type: ignore
                part = 'status,snippet',
                id = video_id
            )
            
            while(upload_status_request.execute()['items'][0]['status']['uploadStatus'] != 'uploaded'):
                time.sleep(0.1)
                log.INFO(f"WAITING FOR UPLOAD: {video_id}")
            log.INFO(f"Upload Complete: {video_id}")
            if thumbnail_pth:            
                try:
                    thumbnail_upload = self.youtube_auth.thumbnails().set( # type: ignore
                        videoId=video_id,
                        media_body=MediaFileUpload(thumbnail_pth)
                    )
                    thumbnail_response = thumbnail_upload.execute()
                    log.INFO(f"Thumbnail uploaded successfully: {thumbnail_response}")
                except Exception as e:
                    log.ERROR(f"Thumbnail upload failed: {e}")
                    return None
            return video_id
        
        except HttpError as exc:
            error_msg = f"YouTube HttpError {getattr(exc.resp, 'status', 'unknown')}: {exc}"
            log.ERROR(f"UPLOAD: upload failed for chapter. {error_msg}")
            
        except Exception as e:
            log.ERROR(f"Video upload failed: {e}")
            return None


    def _get_uploads_playlist_id(self, channel_id: str) -> str:
        """
        Get a playlist ID for the "uploads" playlist for the channel with "channel_id"
        """
        resp = self.youtube_auth.channels().list( # type: ignore
            part="contentDetails",
            id=channel_id
        ).execute()
        
        self.API_CALL_COUNT +=1
        return resp["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]

    def _list_all_video_ids(self, playlist_id: str) -> list:
        """
        Using a playlist_id nad the youtube api, get a list of video_ids from all the videos within
        the playlist
        """
        video_ids = []
        next_page_token = None

        while True:
            resp = self.youtube_auth.playlistItems().list( # type: ignore
                part="contentDetails",
                playlistId=playlist_id,
                maxResults=50,
                pageToken=next_page_token
            ).execute()
            
            self.API_CALL_COUNT +=1

            for item in resp["items"]:
                video_ids.append(item["contentDetails"]["videoId"])

            next_page_token = resp.get("nextPageToken")
            if not next_page_token:
                break

        return video_ids

    def _get_video_comments(self, video_ids: list) -> dict:
        """
        using youtube api and list of video_ids get all the comments under the videso and return them
        as a dict() comments where the key is video_id and value is a list of comments
        """
        comments = {}
        for i in range(0, len(video_ids)):
            try:
                request = self.youtube_auth.commentThreads().list( # type: ignore
                    part="snippet",
                    videoId=video_ids[i],
                    maxResults=100,
                    textFormat="plainText"
                )

                while request:
                    
                    self.API_CALL_COUNT +=1
                    response = request.execute()
                    for item in response["items"]:
                        # comment = item["snippet"]["topLevelComment"]["snippet"]["textDisplay"]
                        comments[video_ids[i]] = item
                    request = self.youtube_auth.commentThreads().list_next(request, response) # type: ignore
            except HttpError as e:
                if e.resp.status == 403 and 'commentsDisabled' in str(e):
                    log.INFO(f"Comments disabled for video {video_ids[i]}. Skipping.")
                else:
                    log.INFO("Some unknown error occured")
                    raise  # re-raise if it's a different error
        return comments

    def _get_videos_statistics(self, video_ids: list) -> dict:
        """
        using video_ids we can get various statistics about the video such as
        title, link, viewCount, likeCount, dislikeCount, commentCount, favoriteCount
        
        using these metrics we can devices the performance of the videos over time using  
        """
        stats = {}
        # You can only request up to 50 IDs at once:
        # also get video title and video link
        for i in range(0, len(video_ids), 50):
            batch = video_ids[i:i+50]
            req = self.youtube_auth.videos().list( # type: ignore
                part="statistics,snippet",
                id=",".join(batch)
            )
            
            self.API_CALL_COUNT +=1
            resp = req.execute()
            for item in resp["items"]:
                vid = item["id"]
                snippet = item["snippet"]
                statistics = item.get("statistics", {})

                stats[vid] = {
                    "title": snippet.get("title"),
                    "link": f"https://www.youtube.com/watch?v={vid}",
                    "viewCount": int(statistics.get("viewCount", 0)),
                    "likeCount": int(statistics.get("likeCount", 0)),
                    "dislikeCount": int(statistics.get("dislikeCount", 0)),
                    "commentCount": int(statistics.get("commentCount", 0)),
                    "favoriteCount": int(statistics.get("favoriteCount", 0)),
                }
        return stats

    def _get_channel_id_by_handle(self, channel_handle: str) -> str:
        """
        Verified youtube chamnels have channel handles that are used in the youtube link instead of 
        channel_id so we need to fire a specific API request to get the channel id from the handle name
        """
        request = self.youtube_auth.search().list( # type: ignore
            part="snippet",
            q=channel_handle,
            type="channel",
            maxResults=1
        )
        
        self.API_CALL_COUNT +=1
        response = request.execute()
        return response['items'][0]['snippet']['channelId']
    
    def _load_templates(self, path: str = config.TEMPLATES_PATH) -> dict:
        with open(path, 'r') as f:
            return json.load(f)
        
    def _get_thumbnail(self, ebook_no: int) -> str:
        templates = self._load_templates()
        if templates.get(f"book_{ebook_no}"):
            thumb_pth = templates[f"book_{ebook_no}"]["thumbnail"]
            return config.BGP_FOLDER + "/" + thumb_pth
        return f"./Data/{config.BGP_FOLDER}/default_thumbnail.jpg"
    
    def _get_tags_list(self, ebook_no: int) -> list:
        templates = self._load_templates()
        if templates.get(f"book_{ebook_no}") and templates.get(f"central_tags"):
            return templates[f"book_{ebook_no}"]["tags"] + templates["central_tags"]
        return ["Missing Tags"]
    
    def _get_discription(self, ebook_no: int ) -> str:
        templates = self._load_templates()
        if templates.get("discription"):
            disc_tpl = templates["discription"]["desc"]
        else:
            return ""
        book_details = self._dbops.get_book_author(ebook_no)
        if book_details is None:
            log.ERROR(f"Book details not found for ebook_no {ebook_no}")
            return "Missing Book Details"
        book_title = book_details[0]
        book_author = book_details[1]
        track_name, track_artist = templates["BGM_mapping"][templates[f"book_{ebook_no}"]["BGM"]]
        
        disc_tpl = disc_tpl.replace("BOOK_NAME", book_title).replace("AUTHOR", book_author).replace("TRACK_NAME", track_name).replace("ARTIST", track_artist)
        return disc_tpl
    
    def _build_youtube_url(self, video_id: str, is_short: bool) -> str:
        if is_short:
            return f"https://www.youtube.com/shorts/{video_id}"
        return f"https://www.youtube.com/watch?v={video_id}"

    def get_video_metadata(self, ebook_no: int, voice_code: int, section_no: int | None = None, use_short: bool = False, short_idx: int | None = None) -> dict:
        book_title, book_author = self._dbops.get_book_author(ebook_no)  # type: ignore
        book_title = book_title.replace('\n', " ")
        voice_name = self.voice_map.get(voice_code, f"Voice {voice_code}")
        description = self._get_discription(ebook_no)
        tags = self._get_tags_list(ebook_no)

        if section_no is None:
            title = f"{book_title} [Full Book Release] by {voice_name}"
            thumbnail_pth = self._get_thumbnail(ebook_no)
        elif use_short:
            assert short_idx is not None, "short_idx is required for short video metadata"
            title = f"{book_title} Chapter {section_no} Short #{short_idx + 1} by {voice_name}"
            thumbnail_pth = ""
        else:
            title = f"{book_title} Chapter {section_no} by {voice_name}"
            thumbnail_pth = self._get_thumbnail(ebook_no)

        metadata = {
            "title": title,
            "description": description,
            "tags": tags,
            "thumbnail_pth": thumbnail_pth,
        }
        return metadata

    def upload_full_video(self, ebook_no: int, voice_code: int) -> str | None:
        metadata = self.get_video_metadata(ebook_no, voice_code)
        signature = "FULL_" + str(ebook_no).zfill(5) + "_" + str(voice_code).zfill(2)
        main_video_file_path = os.path.join(config.OUTPUT_FOLDER, f"Book_{ebook_no}" ,f"{signature}_videosection.mp4")
        main_vid_res = self._upload_video_call(
            main_video_file_path,
            metadata["title"],
            metadata["description"],
            tags=metadata["tags"],
            thumbnail_pth=metadata["thumbnail_pth"],
        )
        log.INFO(f"Uploading main video [{signature}]: Responce {main_vid_res}")
        if main_vid_res is not None:
            main_url = self._build_youtube_url(main_vid_res, False)
            log.INFO(f"Full Video: File Path -> [{main_video_file_path}], title -> [{metadata['title']}], url -> [{main_url}]")
            return main_url
        log.ERROR(f"Failed to upload full video for ebook {ebook_no} and voice code {voice_code}.")
        return None
    
    def upload_single_video(self, category: str, upload_shorts: bool = False) -> bool:
        # Find the next action for category and upload status
        res = self._dbops.get_next_action_category(category, Status.ProcessingStage.PROCESSING, Status.PossibleStates.UPLOAD)
        voice_codes = self._dbops.get_voice_codes(category)
        if res is None or voice_codes is None:
            return False
        ebook_no, chapter_idx = res
        for voice_code in voice_codes:
            video_path = self._dbops.can_start_upload(ebook_no, voice_code, chapter_idx)
            if not video_path:
                continue
            # Update db status in CS table
            self._dbops.update_chapter_status(ebook_no, voice_code, chapter_idx, Status.PossibleStates.UPLOAD, Status.ChapterStatus.UPLOADING)
            metadata = self.get_video_metadata(ebook_no, voice_code, chapter_idx)
            main_vid_res = ""
            try:
                main_vid_res = self._upload_video_call(
                    video_path,
                    metadata["title"],
                    metadata["description"],
                    tags=metadata["tags"],
                    thumbnail_pth=metadata["thumbnail_pth"],
                )
                if main_vid_res is None:
                    log.ERROR(f"Upload[{ebook_no}:{voice_code}:{chapter_idx}]: Failed to upload main video.")
                    self._dbops.mark_chapter_retry(ebook_no, voice_code, chapter_idx, 
                        Status.PossibleStates.UPLOAD, "Upload call returned None", 
                        base_delay=config.RETRY_BASE_DELAY_SECONDS,
                        backoff_factor=config.RETRY_BACKOFF_FACTOR,
                        max_retries=config.RETRY_MAX_ATTEMPTS)
                    continue
                log.INFO(f"Upload[{ebook_no}:{voice_code}:{chapter_idx}]: Response {main_vid_res}")
                main_video_url = self._build_youtube_url(main_vid_res, False)
                self._dbops.update_chapter_status(ebook_no, voice_code, chapter_idx, Status.PossibleStates.UPLOAD, Status.ChapterStatus.COMPLETED, youtube_url=main_video_url)
            except Exception as exc:
                log.ERROR(f"Upload[{ebook_no}:{voice_code}:{chapter_idx}]: Error uploading the video code {exc}")   
                self._dbops.mark_chapter_retry(ebook_no, voice_code, chapter_idx, 
                    Status.PossibleStates.UPLOAD, str(exc), 
                    base_delay=config.RETRY_BASE_DELAY_SECONDS,
                    backoff_factor=config.RETRY_BACKOFF_FACTOR,
                    max_retries=config.RETRY_MAX_ATTEMPTS)
                continue
               
            if upload_shorts:
                shorts_video_paths = self._dbops.can_start_shorts_upload(ebook_no, voice_code, chapter_idx)
                for idx, short_video_file_path in shorts_video_paths:
                    try:
                        self._dbops.update_shorts_status(ebook_no, voice_code, chapter_idx, idx, Status.PossibleStates.UPLOAD, Status.ChapterStatus.UPLOADING)
                        short_metadata = self.get_video_metadata(ebook_no, voice_code, chapter_idx, use_short=True, short_idx=idx)
                        short_vid_res = self._upload_video_call(
                            short_video_file_path,
                            short_metadata["title"],
                            short_metadata["description"],
                            tags=short_metadata["tags"],
                        )
                        if short_vid_res is None:
                            log.ERROR(f"Upload[{ebook_no}:{voice_code}:{chapter_idx}]: Failed to upload shorts for ebook.")
                            self._dbops.mark_short_retry(ebook_no, voice_code, chapter_idx, idx, Status.PossibleStates.UPLOAD, "Short upload returned None")
                            continue
                        log.INFO(f"Upload[{ebook_no}:{voice_code}:{chapter_idx}]: Uploading shorts video #{idx+1}, Response {short_vid_res}")
                        shorts_vid_url = self._build_youtube_url(short_vid_res, True)
                        self._dbops.update_shorts_status(ebook_no, voice_code, chapter_idx, idx, Status.PossibleStates.UPLOAD, Status.ChapterStatus.COMPLETED, youtube_url=shorts_vid_url)
                    except Exception as exc:
                        log.ERROR(f"Upload[{ebook_no}:{voice_code}:{chapter_idx}]: Error uploading short #{idx}: {exc}")
                        self._dbops.mark_short_retry(ebook_no, voice_code, chapter_idx, idx, Status.PossibleStates.UPLOAD, str(exc))

        # Check if all voices for this chapter are done with upload
        all_voices_done = True
        for vc in voice_codes:
            st = self._dbops.get_chapter_state(ebook_no, vc, chapter_idx)
            if not st or st.get('upload_status') not in [Status.ChapterStatus.COMPLETED, Status.ChapterStatus.MANUAL_REVIEW_NEEDED]:
                all_voices_done = False
                break

        if all_voices_done:
            self._dbops._cursor.execute("SELECT max_chapter_idx FROM PROCESSING_STATE WHERE ebook_no = ?", (ebook_no,))
            max_row = self._dbops._cursor.fetchone()
            max_chapter_idx = max_row[0] if max_row else -1

            log.INFO(f"Upload[{ebook_no}]: All voices for chapter {chapter_idx} finished upload. Advancing processing state.")
            if max_chapter_idx > 0 and chapter_idx + 1 >= max_chapter_idx:
                self._dbops.update_processing_state(ebook_no, category, Status.ProcessingStage.COMPLETE, max_chapter_idx)
            else:
                self._dbops.update_processing_state(ebook_no, category, Status.ProcessingStage.PROCESSING, chapter_idx + 1)
        return True

    def upload_single_video_retries(self) -> None:
        upload_chapter_list = self._dbops.get_stage_retries(Status.PossibleStates.UPLOAD)
        for ebook_no, voice_code, chapter_idx, category in upload_chapter_list:
            if category != self.category:
                continue
            try:
                video_path = self._dbops.can_start_upload(ebook_no, voice_code, chapter_idx)
                if not video_path:
                    continue
                self._dbops.update_chapter_status(ebook_no, voice_code, chapter_idx, Status.PossibleStates.UPLOAD, Status.ChapterStatus.UPLOADING)
                metadata = self.get_video_metadata(ebook_no, voice_code, chapter_idx)
                main_vid_res = self._upload_video_call(
                    video_path,
                    metadata["title"],
                    metadata["description"],
                    tags=metadata["tags"],
                    thumbnail_pth=metadata["thumbnail_pth"],
                )
                if main_vid_res is None:
                    log.ERROR(f"Upload[{ebook_no}:{voice_code}:{chapter_idx}]: Failed to upload video for retry")
                    self._dbops.mark_chapter_retry(ebook_no, voice_code, chapter_idx, Status.PossibleStates.UPLOAD, "Retry upload call returned None")
                    continue
                main_video_url = self._build_youtube_url(main_vid_res, False)
                self._dbops.update_chapter_status(ebook_no, voice_code, chapter_idx, Status.PossibleStates.UPLOAD, Status.ChapterStatus.COMPLETED, youtube_url=main_video_url)
            except Exception as exc:
                log.ERROR(f"Upload Retry[{ebook_no}:{voice_code}:{chapter_idx}]: Retry failed: {exc}")
                self._dbops.mark_chapter_retry(ebook_no, voice_code, chapter_idx, Status.PossibleStates.UPLOAD, str(exc)) 