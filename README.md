# tabor-weapon-tester

desktop tool for testing weapon damage in ghosts of tabor. reads chest health from streamer cam via OCR, walks you through a 10-shot test, gives you avg/min/max/stddev.

browse community-submitted results at [data.tabormap.com](https://data.tabormap.com).

## pcvr only

needs the streamer cam to read chest health, which doesn't exist on standalone. pcvr (and the desktop client itself) only.

## usage

just download and run the .exe from releases. no installs needed.

first run does a quick setup wizard. calibrate your screen region in Settings > Calibration once you have the game open.

## notes

site sync uploads completed tests (damage and armor) to a community database if you opt in. off by default. the username field is just a free-text label, not an account, so it's anonymous unless you put something identifying in it.

to re-run the setup wizard (e.g. to change the permanent opt-in/opt-out selection for updates or site sync), delete the config file and relaunch:

```
%APPDATA%\tabor-weapon-tester\config.json
```

deleting this file resets all settings. recalibrate your screen region afterwards.

## armor testing

armor test on the main screen. pick caliber, grade, base damage, start shooting. classifies pen/blunt, tracks pen chance with a wilson confidence interval. runs until that's within ±5% at 90% confidence, so treat the result as an estimate, not an exact number. suspend/resume supported.

## running from source

python 3.11+

```
pip install -r requirements.txt
python main.py
```

## build standalone exe

requires [Tesseract for Windows](https://github.com/UB-Mannheim/tesseract/wiki). install it, then copy the files into the repo before building:
```
New-Item -ItemType Directory -Force -Path "assets\tesseract\tessdata"
Copy-Item "C:\Program Files\Tesseract-OCR\tesseract.exe" "assets\tesseract\"
Copy-Item "C:\Program Files\Tesseract-OCR\*.dll" "assets\tesseract\"
Copy-Item "C:\Program Files\Tesseract-OCR\tessdata\eng.traineddata" "assets\tesseract\tessdata\"
```
```
python -m PyInstaller build.spec --noconfirm
```
