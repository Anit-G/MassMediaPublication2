import torch
print(torch.__version__)
print(torch.cuda.is_available())
print(torch.version.cuda)         # type: ignore # Should output '11.8'

from TTS.TTS import TTS
"""
    Test Script to perform a single run of the TTS pipeline with voice mixing with direct generation calls.
"""

voice_map = {2: "af_aoede", 7: "af_nicole", 9: "af_river", 12:"am_adam", 14:"am_eric", 17:"am_michael", 18:"am_onyx", 23:"bf_isabella", 24:"bf_lily", 25: "bm_daniel", 26:"bm_fable",}
weight_dist = 0.5
mixer = 7
text_sample = "I just wanted to say that I might sound a bit robotic but, I, am, doing, my, best... the, world, is, black, and, white, turned, to, color, only, at, your, sight,... You. my. love. are. my. soulmate. my. reason. to. live!!!"
book_pipe = TTS(weight_dist, mixer)
book_pipe.direct_tts_mixed_generation(list(voice_map.keys()), text_sample=text_sample)
book_pipe.direct_tts_generation(text_sample=text_sample)