# MassMediaPublication
Scrap web content ie books from Project Gutenberg convert it into content for YT and Insta

# The working Aud Vis generator CLI commmand for ffmpeg
Had one really long ffmpeg command that took 10mins to run scrapped the entire Aud vis doesn't look good

Control Flow:
**Scrapper:**

    Status = NULL (update in metadata table)
        - Update status to **REMOVE**: if book not english or has poet/drama in subject
        - Update status to **PARSEABLE**: if book metatdata scrapper passes
    status = PARSABLE (update in metadata table)
        - Update status to **PARSED**: if content scrapper passes properly and add book to ebook_list table
        - Update status to **UNPARSED**: if content scrapper ran with an issue
**TTS:**

    Status = PARSED (update in ebook_list table)
        - update status to **AUDGEN_DONE**: if audio for the book is generated
        - update status to **CURROPTED**: if audio generator ran with issue
**Video_Gen:**

    Status = AUDGEN_DONE (update in ebook_list table)
        - Update status to **VIDGEN_DONE**: done after the video_gen_book is run properly for an entire book

**Monitoring:**

**Posting:**

    We continue to post videos and find the latest video from ebook_lib to upload, once everything is uploaded
        - Update status to **FULL_VIDEO_UPLOADED**: Therefore this book is official done with its cycle.

# GPT PROMPTS

1. **Watermark Prompt (Tiny, minimal mark for videos)**

	Prompt:
	A minimalist line-art design of a stylized Greek nymph (Echo), softly whispering, with gentle soundwaves or ripples emerging from her mouth. Monochrome or soft gradient (pastel blue or lavender), ultra-simple, scalable design with a transparent background. Designed to be a tiny watermark for video content, unobtrusive yet unique.

2. **Logo Prompt (For profile image, branding, icon use)**

	Prompt:
	A dreamy, stylized logo of a Greek nymph in profile (Echo), surrounded by gentle swirling lines symbolizing sound or dreams. The text “Echo Slumber” in elegant serif or calligraphic font below or around the figure. Cool tones like indigo, silver, and pale blue. Soft lighting, minimalist background, suitable for a circular or square frame.

3. **YouTube Banner Prompt (For the channel header)**
	
	Prompt:
	A serene night landscape with a starry sky over a calm sea (Aegean-inspired), with soft moonlight reflecting on the water. A ghostly silhouette of a Greek figure (Echo) standing on a cliff or hill, with glowing soundwaves drifting into the sky. The text “Echo Slumber” in large, elegant font centered or right-aligned. Color palette: deep navy, soft lavender, moonlight white. Wide aspect ratio (2560x1440), designed for YouTube channel banner.

4. **SDXL Prompt for Background Image Generation**
	
	Prompt 1:
	“A [SUBJECT & SYMBOLS] imbued with [MOOD & ATMOSPHERE], rendered in [ART STYLE & TECHNIQUE], composed with the focal element on the [LEFT/RIGHT/CENTER THIRD] to leave negative space for text —style [FLUX_STYLE_TAG] —quality 2 —ar 16:9”  
	—no text, watermark, signature, border, logo, cartoon

	Prompt 2:
	“[SUBJECT & SYMBOLS] under [MOOD & ATMOSPHERE], painted in [ART STYLE & TECHNIQUE], cinematic framing with key element on the [LEFT/RIGHT/CENTER THIRD] to reserve overlay space —v 2 —style [SDXL_STYLE_TAG] —quality 2 —ar 16:9”  
	—no text, watermark, signature, border, logo, cartoon


# To make things better in BG Video

Add Dynamic Visual Variety
Day–Night & Weather Cycles
Use a Minecraft replay/recording mod (e.g. ReplayMod) to record a long “timelapse” of your scene cycling through sunset → night → dawn.
Automate exporting shorter loops (e.g. 2–3 minutes each) via a script so that each video can randomly pick a loop.
Subtle Camera Movements
Pre-define several camera paths (slow pan, gentle orbit, pull-back) in ReplayMod or via command-block scripts.
Write a small Python or bash wrapper that randomly picks one camera path per chapter, so no two videos look identical.
Ambient Particle Effects
Trigger low-frequency particle spawns (fireflies, embers, drifting ash) via an in-world command block clock.
Record that continuously in the replay and slice it automatically when rendering.-

# 🌌 Relaxing Pads for BGM ideas:
Forest Dawn Pad: 
    Gentle piano + morning birds + soft wind rustling leaves.
Mountain Stream Pad: 
    Harp or soft synth chords + flowing river + distant echoing birds.
Rainforest Pad: 
    Ambient strings + rain + distant monkeys/frogs + canopy drip + birds.
Meadow Breeze Pad:
    Light guitar harmonics + meadow wind + bees/grass insects.
Library Pad: 
    Warm synth + muffled fireplace + faint pen scratching + distant murmurs.
Snowy Cabin Pad: 
    Piano + howling winter wind outside + fireplace + wood creaks.
Tropical Beach Pad: 
    Guitar + soft waves + seagulls + wind chimes.
Rain on Lake Pad: 
    Strings + lake water ripples + steady rain.

# 🎭 Thrilling and Adventurous
These pads should create excitement, motion, and energy without overwhelming narration. Think driving rhythms, tense textures, or vast natural backdrops.
Jungle Expedition
	Djembe / hand percussion loop (steady but low)
	Dense jungle ambience (insects, distant monkeys, rustling leaves)
	River stream or distant waterfall
	Subtle brass swells for “heroic” undertone
Desert Quest
	Ethereal oud or sitar plucks (slow, reverb-heavy)
	Soft desert wind whistling
	Shaker or frame drum pulse
	Occasional eagle cry in the distance
High Seas Adventure
	Creaking wooden ship ambience
	Distant gulls, crashing ocean waves
	Slow bodhrán or tom drum heartbeat
	Low drone (synth or cello) for suspense
Mountain Trek
	Cold wind ambience
	Crunching snow/footsteps on gravel intermittently
	Tibetan bells or low throat singing drone
	High-pitched flute notes, sparingly
Lost Temple
	Cave reverb drip sounds
	Sub-bass rumble (for mystery)
	Stone sliding / faint metallic scraping (ancient mechanism feel)
	Sparse choral tones (male choir ahh’s)
	
	
# 🕵️ Mystery and Suspense
Pads here need tension, unease, and curiosity. More subtle, less melodic, relying on textures, drones, and irregular patterns.
Foggy Alley
	Distant footsteps & faint echoing drip water
	Low bass drone (synth pad)
	Rustling paper/trash can lids in the wind
	Sparse piano plinks with reverb
Abandoned Mansion
	Wind blowing through cracks
	Creaking floorboards / distant door slam
	Faint music box melody, slowed and distorted
	Clock ticking intermittently
Shadowed Forest
	Nighttime ambience (owls, crickets, wind in trees)
	Low cello tremolo or bass clarinet breaths
	Occasional twig snap or rustle, panned left/right
	Drone that slightly wavers in pitch for unease
Dark Library
	Flickering candle ambience
	Turning of pages / whispery murmur voices
	Occasional metallic clang (chains, dropped key)
	Low harmonic chimes (glass rubbed rim)
Chamber of Secrets
	Subterranean dripping cave echoes
	Low rumble, like underground shifting stone
	Breathy wind through tunnels
	Sparse reversed cymbal swells
	
	
# 🎨 Whimsical Escapism
Light, dreamy, magical atmospheres. Playful but not cartoonish — should feel imaginative and floaty.
Enchanted Meadow
	Birds chirping in morning light
	Soft harp arpeggios
	Gentle wind chimes
	Flowing brook sounds
Dreamland Lullaby
	Celesta / toy piano twinkles
	Soft synth pads with shimmer
	Humming choir (light female oohs)
	Wind with sparkle effects
Fairy Forest
	Rustling leaves + wind through trees
	Flute trills and light pizzicato strings
	Tinkling bell/glass sounds (like magic dust)
	Distant giggling echoes (subtle, lighthearted)
Sky Voyage
	Whooshing wind as if floating
	Soft accordion or harmonium chord bed
	Metallic shimmer FX (bowed cymbal)
	Seagull-like echoes but dreamy
Magical Market
	Crowd murmurs (friendly, busy, indistinct)
	Dulcimer or zither plucks
	Tambourine jingle accents
	Colorful flute phrases
	
	
# 📚 Literary Masterpieces
This theme should evoke timelessness, elegance, and depth — leaning more classical, intellectual, or refined soundscapes.
Classical Study
	Fireplace crackle
	Pen writing on parchment
	Soft harpsichord or string quartet phrases
	Grandfather clock ticking
Romantic Era Ambience
	Gentle piano arpeggios (Chopin-esque)
	Subtle rain outside window
	Faint thunder in the distance
	Ambient reverb room tone (concert hall feel)
Epic Poetry
	Deep choral drones (male/female voices blended)
	Low strings sustain (cellos, basses)
	Wind sweeping across landscapes
	Occasional distant church bell toll
Victorian Parlor
	Teacup clinks / subtle murmuring voices
	String quartet waltz loop (light, in background)
	Fireplace and chair creaks
	Clock pendulum swinging
Philosopher’s Study
	Candle crackle and turning pages
	Subtle Gregorian chant-style drone
	Ambient reverb space (stone-walled study)
	Distant thunderstorm outside

Note: Each BMG needs to be set to an approprate volume so as to work with normalization in the videogeneration and come out ok

# Template prompt for Image generation prompt for ChatGPT

You are a professional image-prompt engineer for AI art models. Produce a single image-generation prompt optimized for a YouTube audiobook thumbnail that **includes** a stylized representation of the book title inside the image. Use these placeholders:

Book title: {{BOOK_TITLE}}
Channel theme: {{CHANNEL_THEME}}

Requirements:
- Output only one image-generation prompt string (no explanation).
- 16:9 aspect ratio, high resolution, bold composition.
- Create a central focal element that captures the book's mood and {{CHANNEL_THEME}}.
- Integrate the book title as an artistic, legible element (large, bold, high-contrast typography effect — e.g., engraved, glowing, stencil) but avoid exact readable lettering the model struggles with; design it as a stylized graphic element rather than precise small text.
- Color palette, lighting, camera angle, props, and mood should be optimized for thumbnails (high contrast, simple shapes).
- Add in small text the word "Audiobook" in a reserved corner
- End with negatives: "no watermarks, no signatures, avoid small unreadable text".
- Don't include anything NSFW and construct a prompt with sufficient detail to bypass or be complient with copyright policy. Replace words that would set copyright policy off with descriptions instead that is complient.

Write the final prompt as one compact sentence or short paragraph.


# Find the next ebooks to operated on with highest rating and certain status
SELECT ebook_no, category, no_rating
FROM (
  SELECT ebook_no, category, no_rating,
         ROW_NUMBER() OVER (PARTITION BY category ORDER BY no_rating DESC, ebook_no ASC) AS rn
  FROM ebook_list
  WHERE status = 'PARSED'
) t
WHERE rn = 1;

# Youtube Map:
```
    Shortform  Categoris                   [voice_codes]       YouTube Channel ID         Channel Name               Channel Tag  
    ---------  --------------------------  ------------------  -------------------------  -------------------------  -------------------------

    cat(RS)    Relaxing and Soothing       [3, 7]              UCXeqq2XcvF7jjEcv35dPl8A   Echo's Slumber             @EchoSlumber
    cat(MS)    Mystery and Suspense        [18, 26]            UCfOw-0ovjVZSE8HvaCNJJ_Q   Erebus Echoes              @ErebosEchoes
    cat(WE)    Whimsical escapism          [20, 23]            UCKpi4fdhxKbO_DWUD3FODTA   MoonBerry Echoes           @MoonBerryEchoes
    cat(LM)    Litrary Masterpieces        [17, 22]            UChDu5fX4ICAQSgdT653TGzA   Marrow & Manuscripts       @MarrowManuscripts

    DECOD[cat(TA)]    Thrilling and Adventurous   [15,19]             UCGKLnKX4AF6r1Fz86BvUPEw   ------               @OrpheusOdes
```

# Instructions

**How to setup the tokens and credentials**

	Credentials need to be setup via GCP Console or Google Cloud Platform Console, you can create a new set of credentials via the API & Services -> Credentials -> Create Credentials, OAuth 2.0 Client IDs will be created which will be unique for a specific set of services in my case Youtube Data API.

	After creation of the Client ID for Desktop or Conatiner or whatever you will have the option to dowload a json which will be used as credentials for the API usage. (keep it safe and off the internet it is a secret)

	Secondly is the token: this is to give autherization via the client IDs for a specific user for a specific scope or type of API use again like the Youtube data API in my case.
	The code (UpMonYoutube) will use the credentials linked (./Data/Secrets/client_secrets.json) to my google account to raise request to get access to specific API scopes on that a brand account or gmail account or youtube channel of my wish. This will create a web pop-up from google asking for consent to give API scope permission to an account.

	Essentially since there are 5 accounts/Youtube Channels this request will come up five times and each time it comes the google pop-up may show a set of brand accounts or youtube channels to show from. Choose the right account for the right pop-up, if you need help there will be a prompt in the terminal to tell you which to choose. 

### Samples for write_path
```
print(write_path(1,2,3,Status.PossibleStates.AUDIO_GEN))
print(write_path(1,2,3,Status.PossibleStates.AUDIO_GEN, headsectionFlag = True))
print(write_path(1,2,3,Status.PossibleStates.AUDIO_GEN, shorts_idx = 1))
print(write_path(1,2,3,Status.PossibleStates.VIDEO_GEN))
print(write_path(1,2,3,Status.PossibleStates.VIDEO_GEN, shorts_idx = 2))
print(write_path(1,2,3,Status.PossibleStates.UPLOAD))
print(write_path(1,2,3,Status.PossibleStates.UPLOAD, shorts_idx = 3))

print(write_path(1,2,3,Status.PossibleStates.VIDEO_GEN, headsectionFlag = True))
print(write_path(1,2,3,Status.PossibleStates.UPLOAD, headsectionFlag = True))
print(write_path(1,2,3,Status.PossibleStates.AUDIO_GEN, headsectionFlag = True, shorts_idx = 4))
print(write_path(1,2,3,Status.PossibleStates.VIDEO_GEN, headsectionFlag = True, shorts_idx = 4))
print(write_path(1,2,3,Status.PossibleStates.UPLOAD, headsectionFlag = True, shorts_idx = 4))

"""
Data/AudFiles/Book_1/00001_02_003_chapsection.wav
Data/AudFiles/Book_1/00001_02_003_headsection.wav
Data/AudFiles/Book_1/00001_02_003_Shorts/short_01.wav
Data/OutputVideos/Book_1/00001_02_003_videosection.mp4
Data/OutputVideos/Book_1/00001_02_003_Shorts/00001_02_003_videoshort_02.mp4
Data/OutputVideos/Book_1/00001_02_003_videosection.mp4
Data/OutputVideos/Book_1/00001_02_003_Shorts/00001_02_003_videoshort_03.mp4
Data/OutputVideos/Book_1/00001_02_003_videosection.mp4
Data/OutputVideos/Book_1/00001_02_003_videosection.mp4
Data/AudFiles/Book_1/00001_02_003_Shorts/short_04.wav
Data/OutputVideos/Book_1/00001_02_003_Shorts/00001_02_003_videoshort_04.mp4
Data/OutputVideos/Book_1/00001_02_003_Shorts/00001_02_003_videoshort_04.mp4
"""
```