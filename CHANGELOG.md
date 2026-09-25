# Historia wersji

Każde wydanie ma własny numer. Opis zmian dla danej wersji trafia automatycznie
do treści wydania na GitHubie (skrypt `tools/create_release.py` czyta ten plik).

## 1.0.9 — 25 września 2026

**Nowe**

- **Statystyki dla zaznaczonego fragmentu wykresu.** Nowe pole „Zaznacz fragment”: zaznaczasz
  myszą kawałek przejazdu (np. jedno przyspieszanie) i pod wykresem pojawiają się minimum,
  średnia i maksimum każdego widocznego parametru — liczone wyłącznie z zaznaczonych próbek.
  Krawędzie zaznaczenia można przesuwać myszą, a złapanie środka przesuwa całe zaznaczenie po
  logu. Zaznaczenie działa też przy osi obrotów (wtedy zakres znaczy „obroty od–do”).
  Przycisk „Wyczyść” usuwa zaznaczenie, a zmiana osi X czyści je samo — stare jednostki
  przestałyby pasować.

## 1.0.8 — 25 września 2026

**Ulepszenia**

- **Podpowiedź tłumaczy pionowe kreski.** Przy osi obrotów, gdy w logu są prawdziwe
  skoki (np. odcięcie wtrysku: obciążenie spada ze 120% do 14% w jednej próbce),
  program mówi wprost, że to dane z logu, a nie sklejone przebiegi — żeby nie trzeba
  było się domyślać ani zgłaszać tego jako błędu.
- **Autotest każdej paczki sprawdza kursor przy obu osiach** — w widoku pojedynczego
  logu i w oknie porównania. Usterka z 1.0.6 („kursor: 4640,00 s” zamiast prawdziwego
  czasu zdarzenia) zostałaby teraz wychwycona automatycznie przy budowaniu wersji:
  autotest pilnuje, że przy osi obrotów do paska statusu trafia czas zdarzenia
  i wartość obrotów, a nie sama pozycja na osi.

## 1.0.7 — 25 września 2026

**Naprawione**

- **Obroty bez miejsc po przecinku.** Przy osi obrotów etykieta kursora pokazywała
  „4 640,00 obr/min”, a dymek „Obroty = 4 640,000 obr/min”. Obroty silnika to wartość
  całkowita, więc teraz jest „4 640 obr/min” — i w wykresie nakładanym, i w pasmach,
  i w dymku. Przy osi czasu bez zmian: tam setne sekundy zostają („30,00 s”).

**Sprawdzone przy okazji zgłoszeń (program działa poprawnie, bez zmian w kodzie)**

- Pionowe kreski na wykresie przy osi obrotów to prawdziwe skoki w danych
  (np. odcięcie wtrysku — obciążenie spada w jednej próbce ze 130% do 10%).
  Program rozcina tylko sztuczne połączenia między przebiegami i robi to poprawnie —
  sprawdzone osobno dla każdego parametru w obu logach przykładowych.
- Komunikat „logi mogą być z różnych przejazdów” przy niskiej zgodności dopasowania
  to nie błąd: przy dwóch różnych przejazdach program mówi o tym wprost, zamiast
  dopasowywać na siłę.

## 1.0.6 — 25 września 2026

**Naprawione (na podstawie zgłoszeń)**

- **Pasek statusu w oknie porównania przy osi obrotów.** Pokazywał obroty jako czas —
  „kursor: 4640,00 s” zamiast prawdziwego czasu zdarzenia. Teraz przy osi obrotów widać
  poprawnie czas i obroty w miejscu kursora, tak samo jak w widoku pojedynczego logu.
- **Nagłówki kolumn tabeli nie gubią już numeru grupy.** Przy wąskich kolumnach program
  ucinał tekst w połowie — było „Grupa A: 0”, a numer grupy (020/115/118) znikał.
  Teraz skrót zachowuje numer: „Gru…020”.
- **Liczby po polsku w komunikatach.** „Zgodność 0,61”, „przesunięty o −5,04 s”,
  „czas trwania 93,2 s” — wcześniej w tych miejscach była kropka dziesiętna.
- **Odmiana słowa „przebieg”** w podpowiedzi przy osi obrotów — jest „7 przebiegów”,
  a nie „7 przebiegi”.

## 1.0.5 — 24 września 2026

**Nowe**

- **Porównanie logów — wybór logu bazowego.** W lewym panelu wybierasz, do którego logu
  porównywane są pozostałe. Różnice (Δ) liczone są zawsze jako: drugi log − log bazowy,
  a nagłówki tabeli i statystyk pokazują, względem czego liczą (np. `Δ A−B`).
- **Automatyczne dopasowanie w czasie.** Program sam znajduje przesunięcie, przy którym
  oba logi pokrywają się najlepiej (porównuje wspólne parametry po kształcie, odpornie na
  różne tempo jazdy) i od razu tak ustawia wykresy. Przycisk **„Dopasuj w czasie”**
  przelicza to ponownie, a obok widać wynik, np.
  „Dopasowano w czasie: log B przesunięty o −5,04 s (zgodność 0,61, 4 wspólnych parametrów)”.
  Gdy logi pochodzą z różnych przejazdów, program mówi o tym wprost zamiast dopasowywać na siłę.
- **Oś obrotów w porównaniu działa** — wcześniej przełączenie osi na obroty w oknie
  porównania kończyło się cichym błędem i wykres się nie zmieniał. Teraz oba logi można
  zestawić po obrotach silnika (charakterystyka parametru niezależnie od momentu jazdy).
  Przy osi obrotów pole przesunięcia jest wyszarzone — tam przesunięcie w czasie nie ma sensu.

## 1.0.4 — 23 września 2026

**Poprawione**

- **Lista parametrów w porównaniu logów** pokazuje teraz przy każdej pozycji, gdzie występuje:
  `[A+B]` — w obu logach, `[tylko B]` — tylko w jednym. Znacznik stoi **na początku** pozycji,
  więc nie zniknie, gdy nazwa parametru jest ucinana przy wąskim panelu. Nad listą jest legenda.

## 1.0.3 — 23 września 2026

**Nowe**

- **„Rysowanie: Średnia”** — trzeci tryb rysowania dla osi obrotów. Uśrednia wartości
  w przedziałach obrotów i pokazuje gładką charakterystykę: „ile ten parametr wynosi przy
  danych obrotach”. Bez zygzaków i pionowych kresek. Tryby do wyboru: **Linia** (surowa,
  dla osi czasu), **Punkty** (rzeczywisty rozrzut próbek) i **Średnia** (charakterystyka).

**Naprawione**

- **Program mieści się na małym ekranie.** Pasek opcji nad wykresem wymuszał szerokość
  1727 px, więc na typowym laptopie warsztatowym (1366 × 768) okno nie mieściło się
  w ekranie i tabela była ucięta. Teraz kontrolki zawijają się do kolejnych linii,
  a okno da się zwężyć do ~620 px.
- **Tabela dopasowuje się do szerokości okna.** Kolumny zwężają się proporcjonalnie, więc
  wszystkie mieszczą się bez przewijania w poziomie; na szerokim ekranie wracają do
  wygodnych szerokości. To samo dotyczy tabeli różnic w porównaniu logów.
- **Krótsze etykiety** w paskach opcji („Przebiegi”, „Normalizuj”, „Przyciągaj”,
  „Tabela za kursorem”, „Kolorowanie”) — pełne wyjaśnienie w podpowiedziach pod kursorem.

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
