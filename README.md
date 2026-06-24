# tabor-weapon-tester

desktop tool for testing weapon damage in ghosts of tabor. reads chest health from streamer cam via OCR, walks you through a 10-shot test, gives you avg/min/max/stddev.

## usage

just download and run the .exe from releases. no installs needed.

first run does a quick setup wizard. calibrate your screen region in Settings > Calibration once you have the game open.

## running from source

python 3.11+

```
pip install -r requirements.txt
python main.py
```

build standalone exe:
```
python -m PyInstaller build.spec --noconfirm
```
