import Utils.Config_vars as config
import Utils.Central_Logger as log

from TTS.TTS import TTS
"""
    Test Script to perform a single run of the TTS pipeline with voice mixing with direct generation calls.
"""
# voice_map = {1: "af_alloy", 2: "af_aoede", 3: "af_bella", 4: "af_heart", 5: "af_jessica", 6: "af_kore", 7: "af_nicole", 8: "af_nova", 9: "af_river", 10:"af_sarah",
#             11:"af_sky", 12:"am_adam", 13:"am_echo", 14:"am_eric", 15:"am_fenrir", 16:"am_liam", 17:"am_michael", 18:"am_onyx", 19:"am_puck", 20:"am_santa",
#             21:"bf_alice", 22:"bf_emma", 23:"bf_isabella", 24:"bf_lily", 25:"bm_daniel", 26:"bm_fable", 27:"bm_george", 28:"bm_lewis",}
voice_map = {2: "af_aoede", 7: "af_nicole", 9: "af_river", 12:"am_adam", 14:"am_eric", 17:"am_michael", 18:"am_onyx", 23:"bf_isabella", 24:"bf_lily", 25: "bm_daniel", 26:"bm_fable",}
weight_dist = 0.5
mixer = 7
book_pipe = TTS(weight_dist, mixer)
# if(config.CONVERT_SUMMS):
#     try: 
#         log.INFO("Running TTS BE for Summary to Aud conversion")   
#         book_pipe.sum_to_aud()
#     except Exception as e:
#         log.ERROR(f"Exception was raised during operation of the sum_to_aud: {e}")
    
# while config.TTS_INSTANCE:
log.INFO("Starting new instance of BE TTS")
try:    
    # has to be a valid map gotten from https://huggingface.co/hexgrad/Kokoro-82M/tree/main/voices
    book_pipe(list(voice_map.keys()), "cat(RS)")
except Exception as e:
    log.ERROR(f"Exception was raised during operation of the BE: {e}")