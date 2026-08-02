import os
import json, time

import Utils.Central_Logger as log
import Utils.Config_vars as config

from Utils.DB_Operations import DBOps, Status
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.errors import HttpError

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
        
        self._dbops._cursor.execute("SELECT yt_hash FROM YOUTUBE_MAP WHERE category = ?", (self.category,))
        res = self._dbops._cursor.fetchone()
        if not res:
            log.ERROR(f"Upload[{self.category}]: Missing category in YOUTUBE_MAP table")
            os.abort()
        return res[0]
    
    def _get_authenticated_service(self) -> None:
        creds = None
        token = self._dbops.get_channel_token(self.MY_CHANNEL_ID)
        if token:
            creds = Credentials.from_authorized_user_info(token, self.SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                    # Save refreshed token immediately
                    self._dbops.set_channel_token(self.MY_CHANNEL_ID, creds.to_json())
                except Exception as e:
                    log.ERROR(f"Token refresh failed for channel {self.MY_CHANNEL_ID}: {e}")
                    # In PRD, never fall through to interactive flow — hard abort
                    raise RuntimeError(
                        f"Cannot refresh token for {self.MY_CHANNEL_ID}. "
                        f"Re-authorize manually by deleting and running locally."
                    )
            else:
                # No token at all — only acceptable before first deploy
                if os.environ.get("ENV") == "production":
                    log.ERROR(f"!!! WE ARE FUCKED, CREDS ARE EXPIRED OR MISSING !!! \n Channel ID {self.MY_CHANNEL_ID}")
                    raise RuntimeError(
                        f"No valid token for {self.MY_CHANNEL_ID} in production. "
                        "Run auth flow locally first."
                    )
                client_config = self._dbops.get_client_secret()
                log.WARNING(f"Client Config: {client_config}")
                flow = InstalledAppFlow.from_client_config(
                    client_config, self.SCOPES
                )
                creds = flow.run_local_server(port=0)
                self._dbops.set_channel_token(self.MY_CHANNEL_ID, creds.to_json())

        self.youtube_auth = build("youtube", "v3", credentials=creds)

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
            if video_path is None:
                return False
            # Update db status in CS  table
            self._dbops.update_chapter_status(ebook_no,voice_code,chapter_idx, Status.PossibleStates.UPLOAD, Status.ChapterStatus.UPLOADING)
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
                    return False
                log.INFO(f"Upload[{ebook_no}:{voice_code}:{chapter_idx}]: Responce {main_vid_res}")
                main_video_url = self._build_youtube_url(main_vid_res, False)
                self._dbops.update_chapter_status(ebook_no,voice_code,chapter_idx, Status.PossibleStates.UPLOAD, Status.ChapterStatus.COMPLETED, youtube_url=main_video_url)
            except Exception as exc:
                log.ERROR(f"Upload[{ebook_no}:{voice_code}:{chapter_idx}]: Error uploading the video code {exc}")   
                self._dbops.mark_chapter_retry(ebook_no, voice_code, chapter_idx, 
                    Status.PossibleStates.UPLOAD, str(exc), 
                    base_delay=config.RETRY_BASE_DELAY_SECONDS,
                    backoff_factor=config.RETRY_BACKOFF_FACTOR,
                    max_retries=config.RETRY_MAX_ATTEMPTS,)       
               
            if upload_shorts:
                shorts_video_paths = self._dbops.can_start_shorts_upload(ebook_no, voice_code, chapter_idx)
                if shorts_video_paths == []:
                    return False

                for idx, short_video_file_path in shorts_video_paths:
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
                        return False
                    log.INFO(f"Upload[{ebook_no}:{voice_code}:{chapter_idx}]: Uploading shorts video #{idx+1}, Responce {short_vid_res}")
                    shorts_vid_url = self._build_youtube_url(short_vid_res, True)
                    self._dbops.update_shorts_status(ebook_no,voice_code,chapter_idx,idx, Status.PossibleStates.UPLOAD, Status.ChapterStatus.COMPLETED, youtube_url=shorts_vid_url)
        
        # Update Processing State
        self._dbops.update_processing_state(ebook_no, category, Status.ProcessingStage.PROCESSING ,chapter_idx+1)
        return True

    def upload_single_video_retries(self) -> None:
        upload_chapter_list = self._dbops.get_stage_retries(Status.PossibleStates.UPLOAD)
        for ebook_no, voice_code, chapter_idx, category in upload_chapter_list:
            try:
                self._dbops.update_chapter_status(ebook_no,voice_code,chapter_idx, Status.PossibleStates.UPLOAD, Status.ChapterStatus.UPLOADING)
                video_path = self._dbops.can_start_upload(ebook_no, voice_code, chapter_idx)
                if video_path is None:
                    continue
                metadata = self.get_video_metadata(ebook_no, voice_code, chapter_idx)
                main_vid_res = ""
                main_vid_res = self._upload_video_call(
                    video_path,
                    metadata["title"],
                    metadata["description"],
                    tags=metadata["tags"],
                    thumbnail_pth=metadata["thumbnail_pth"],
                )
                if main_vid_res is None:
                    log.ERROR(f"Upload[{ebook_no}:{voice_code}:{chapter_idx}]: Failed to upload video for retry")
                    continue
                main_video_url = self._build_youtube_url(main_vid_res, False)
                self._dbops.update_chapter_status(ebook_no,voice_code,chapter_idx, Status.PossibleStates.UPLOAD, Status.ChapterStatus.COMPLETED, youtube_url=main_video_url)
            except Exception as exc:
                log.ERROR(f"Upload[{ebook_no}:{voice_code}:{chapter_idx}]: Error uploading retry the video code {exc}")   
                self._dbops.mark_chapter_retry(ebook_no, voice_code, chapter_idx, 
                    Status.PossibleStates.UPLOAD, str(exc), 
                    base_delay=config.RETRY_BASE_DELAY_SECONDS,
                    backoff_factor=config.RETRY_BACKOFF_FACTOR,
                    max_retries=config.RETRY_MAX_ATTEMPTS,) 