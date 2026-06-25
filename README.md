# tabor-weapon-tester

desktop tool for testing weapon damage in ghosts of tabor. reads chest health from streamer cam via OCR, walks you through a 10-shot test, gives you avg/min/max/stddev.

## usage

just download and run the .exe from releases. no installs needed.

first run does a quick setup wizard. calibrate your screen region in Settings > Calibration once you have the game open.

## notes

site sync (community database upload) isn't implemented yet — enabling it won't do anything or may error. leave it off.

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
