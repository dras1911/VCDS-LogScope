# Historia wersji

Każde wydanie ma własny numer. Opis zmian dla danej wersji trafia automatycznie
do treści wydania na GitHubie (skrypt `tools/create_release.py` czyta ten plik).

## 1.0.2 — 23 września 2026

**Naprawione**

- **Pionowe „ściany” na wykresie przy osi obrotów.** Rysując linią, program łączył ze sobą
  próbki, które dzieliły dziesiątki sekund (np. dwa biegi jałowe w różnych momentach logu) —
  powstawały pionowe kreski wyglądające jak pętle. Teraz linia jest w takich miejscach
  rozcinana. Zmiana dotyczy **wyłącznie osi obrotów** — przy osi czasu linia zostaje ciągła,
  bo tam kolejność próbek jest prawdziwa.
- **Przesuwanie kursora strzałkami przy przybliżeniu.** Kursor wyjeżdżał poza widok i nie było
  widać, w którym miejscu logu jesteśmy. Teraz widok przesuwa się razem z kursorem — tak samo
  jak przy klikaniu wierszy tabeli.
- **Opisy i podpowiedzi** nie odwołują się już do innych programów — narzędzie jest opisane
  na własnych zasadach (dotyczy opisu wydania, README i podpowiedzi w oknie programu).

## 1.0.1 — 23 września 2026

**Naprawione (na podstawie zgłoszeń)**

- **Wykres przy osi obrotów nie tworzy już zygzaków.** Ten sam parametr przy tych samych
  obrotach może mieć różne wartości (np. kąt wyprzedzenia zapłonu zależy też od obciążenia),
  więc linia łącząca próbki skakała. Teraz przy osi obrotów program domyślnie rysuje punkty,
  a linię można włączyć przełącznikiem „Rysowanie”.
- **Kliknięcie wiersza tabeli przy osi obrotów** ustawia kursor na właściwym wierszu.
  Wcześniej program odczytywał czas z powrotem z osi obrotów i trafiał na pierwszą próbkę
  o tych samych obrotach — czyli na inny wiersz, często z początku logu.
- **Kursor nie zniknie z ekranu** — jeśli wiersz tabeli wypada poza oglądany zakres osi X,
  widok sam się dosuwa (bez zmiany przybliżenia).
- **Porównanie logów pokazuje wszystkie parametry z obu plików**, także te obecne tylko
  w jednym z nich (oznaczone „tylko A” / „tylko B”). Wcześniej lista ograniczała się do
  parametrów wspólnych — przy dwóch różnych sterownikach zostawały 4 z 17 pozycji.

**Nowe**

- **Widok pasm** — każdy parametr w osobnym pasie z własną skalą i wspólnym kursorem;
  wartość przy kursorze w nagłówku pasa. Rozwiązuje problem nakładania się linii.
- Przełącznik **„Rysowanie: Linia / Punkty”** w widoku pojedynczego logu i w porównaniu.
- **Numer wersji** w oknie „O programie” oraz osobne wydanie na GitHubie dla każdej wersji
  (`v1.0.1`, `v1.0.2`, …) — można wrócić do starszej wersji, jeśli nowsza coś popsuje.

## 1.0.0 — 22 września 2026

Pierwsze wydanie.

- Wykres nakładany ze wszystkimi parametrami i kursorem pomiarowym (czas + obroty przy osi X).
- Oś X przełączana między czasem a obrotami; podział danych na przebiegi.
- Tabela z kolorowaniem narastającym, strzałkami zmian i podświetlaniem wiersza.
- Porównanie dwóch lub więcej logów: nakładka, tabela różnic, statystyki, przesunięcie czasowe.
- Wersja dla Windows 7 / 8 / 8.1 oraz wersja przenośna (katalog).
