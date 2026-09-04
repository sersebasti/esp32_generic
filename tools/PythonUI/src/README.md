OS WINDOWS

per eseguire con python:
python -m venv venv
.\venv\Scripts\Activate
pip install --upgrade pip
pip install -r requirements.txt

per creare eseguibile:
pyinstaller --onefile --add-data "templates;templates" --add-data "static;static" main.py




OS LINUX
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

per creare eseguibile (occore servire creare ambiente vituale e installar le librerie):
python -m PyInstaller --onefile --add-data "templates:templates" --add-data "static:static" main.py