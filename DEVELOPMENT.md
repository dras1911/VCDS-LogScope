# VCDS LogScope — informacje techniczne

Dokument dla osób, które chcą zbudować program ze źródeł lub coś w nim zmienić.
Zwykłym użytkownikom wystarczy gotowy plik `.exe` ze [strony wydania](../../releases/latest).

## Środowisko

```
uv venv --python 3.11 .venv
uv pip install --python .venv\Scripts\python.exe PySide6 pyqtgraph numpy pytest pillow pyinstaller
```

Dla wersji **Windows 7/8** potrzebne jest drugie, starsze środowisko
(Python 3.8 + Qt 5.15 — ostatnie wydania wspierające Windows 7):

```
uv venv --python 3.8 .venv38
uv pip install --python .venv38\Scripts\python.exe PySide2==5.15.2.1 pyqtgraph==0.13.3 "numpy<1.25" pyinstaller==5.13.2
```

## Uruchamianie ze źródeł

```
run.bat                                            # Windows (pythonw, bez konsoli)
.venv\Scripts\python.exe -m vcds_viewer plik.csv   # z konsolą
```

## Testy

```
.venv\Scripts\python.exe -m pytest tests\ -q       # 18 testów
```

Testy pokrywają: parser (nagłówki PL/EN/DE, kodowania, grupy 1/2/3, jednostki, kolumny binarne,
pliki bez danych, przecinek dziesiętny), model (oś RPM, dopasowanie parametrów między logami,
wartość obrotów przy kursorze) oraz przypisywanie kolorów.

## Budowanie wersji .exe

```
.venv\Scripts\python.exe tools\build_exe.py            # katalogowa (Windows 10/11)
.venv\Scripts\python.exe tools\build_exe.py --onefile  # jednoplikowa (Windows 10/11)
.venv\Scripts\python.exe tools\build_exe.py --legacy   # jednoplikowa dla Windows 7/8
.venv\Scripts\python.exe tools\build_exe.py --all      # wszystkie trzy
```

Skrypt rysuje ikonę (QPixmap → PNG → `.ico` przez Pillow), buduje paczkę PyInstaller,
**uruchamia autotest gotowego .exe** i tworzy skrót na pulpicie.

Autotest (działa bez GUI — przydatny po każdej zmianie):

```
"dist\onefile\VCDS LogScope.exe" --selftest tests\data\przyklad.csv build\selftest
"dist\onefile\VCDS LogScope.exe" --selftest-gui tests\data\przyklad.csv   # pełne GUI, zamyka się po 4 s
```

Pierwszy tryb wczytuje log, buduje wykres i widok porównania, zapisuje zrzuty PNG oraz
`selftest_report.txt`. Drugi uruchamia **prawdziwe okno z pętlą zdarzeń** — tylko on wyłapuje
błędy startu GUI (np. `QApplication.exec` w Qt 5 to `exec_`). `build_exe.py` uruchamia oba
po każdym budowaniu.

### Pułapki pakowania (sprawdzone boleśnie)

- **Nie wykluczaj `PySide6.QtOpenGL` / `QtOpenGLWidgets`** — pyqtgraph importuje je
  bezwarunkowo (`pyqtgraph/Qt/OpenGLHelpers.py`) i aplikacja nie wystartuje
  (`ModuleNotFoundError: No module named 'PySide6.QtOpenGL'`).
- Punkt wejścia dla PyInstallera to **`vcds_logscope.py`** w katalogu głównym (absolutny import).
  Budowanie z `vcds_viewer/__main__.py` (import względny) daje paczkę **bez DLL Qt**.
- Wersja `--windowed` nie ma konsoli, więc `print` nic nie pokaże — dlatego autotest
  zapisuje raport do pliku.

## Warstwa zgodności Qt

`vcds_viewer/qt.py` importuje PySide6 (Qt 6) albo PySide2 (Qt 5.15) — reszta kodu nie wie,
na której wersji działa. Różnice, które ta warstwa ukrywa:

- `QAction` w Qt 5 jest w `QtWidgets`, w Qt 6 w `QtGui`,
- brak typu `Qt.PenStyle` w Qt 5 (używamy `int`).

## Struktura projektu

```
vcds_viewer/
  qt.py          # warstwa zgodności PySide6 / PySide2
  parser.py      # czytanie CSV z VCDS (kodowania, grupy, jednostki, bloki)
  model.py       # model danych: LogData / Group / Channel, oś X czas|RPM, przebiegi obrotów
  colors.py      # paleta kolorów parametrów + unikalne kolory serii
  chartview.py   # wykres nakładany, kursor, dymek, etykieta przy osi X
  bandview.py    # widok pasm: jeden parametr = jeden wykres, wspólny kursor
  tableview.py   # tabela: heatmapa, strzałki zmian, nagłówek grupowy
  compare.py     # porównanie logów: nakładka + tabela różnic + statystyki
  logview.py     # widok jednego logu (wykres + panel parametrów + tabela)
  mainwindow.py  # okno główne, karty, menu, drag & drop, ostatnie pliki
  theme.py       # motyw ciemny/jasny
  formatting.py  # polskie formatowanie liczb (1 234,56)
tests/           # testy parsera, modelu i kolorów (+ przykładowy log)
tools/           # build_exe.py, create_release.py, screenshot.py, make_example.py
```

## Wydanie nowej wersji

```
.venv\Scripts\python.exe tools\build_exe.py --all --no-shortcut
powershell -c "Compress-Archive -Path 'dist\VCDS LogScope\*' -DestinationPath 'dist\VCDS-LogScope-1.0-portable.zip' -Force"
.venv\Scripts\python.exe tools\create_release.py --tag v1.0
```

`create_release.py` korzysta z poświadczeń zapisanych przez Git Credential Manager
(nic nie trzeba wpisywać), tworzy wydanie i podmienia załączniki.

## Zrzuty ekranu do weryfikacji

```
QT_QPA_PLATFORM= .venv\Scripts\python.exe tools\screenshot.py       # wszystkie widoki
QT_QPA_PLATFORM= .venv\Scripts\python.exe tools\shot_log.py plik.csv nazwa
```

Uwaga: `QT_QPA_PLATFORM=offscreen` **nie nadaje się** do oceny wyglądu — brak bazy czcionek,
tekst renderuje się jako prostokąty. Zrzuty robimy na normalnym backendzie przez `widget.grab()`.

## Przykładowy log w repozytorium

`tests/data/przyklad.csv` to zanonimizowany log (bez VCID, numeru sterownika i daty sesji).
Odtworzenie z logu źródłowego:

```
.venv\Scripts\python.exe tools\make_example.py LOG-zrodlowy.CSV tests\data\przyklad.csv
```

Logi użytkownika (`LOG-*.CSV` w katalogu głównym) są ignorowane przez git — zawierają
identyfikatory pojazdu.
