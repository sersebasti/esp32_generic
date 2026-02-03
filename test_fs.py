# test_fs.py - Test scrittura su filesystem ESP32
try:
    with open("scope/test_write.txt", "w") as f:
        f.write("test\n")
    print("File scritto correttamente.")
except Exception as e:
    print("Errore di scrittura:", repr(e))

try:
    import os
    print("Contenuto cartella scope:", os.listdir("scope"))
except Exception as e:
    print("Errore lettura cartella:", repr(e))
