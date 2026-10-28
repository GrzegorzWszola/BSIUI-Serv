# 💬 Messenger API — BSIUI

Serwer komunikatora napisany w **FastAPI + SQLModel + SQLite**.  
Klienci (zewnętrzne aplikacje kolegów) komunikują się z serwerem przez HTTP — polling co N sekund.

---

## 📋 Spis treści

- [Wymagania i instalacja](#wymagania-i-instalacja)
- [Uruchamianie](#uruchamianie)
- [Architektura i flow](#architektura-i-flow)
- [Endpointy](#endpointy)
  - [Auth — rejestracja i logowanie](#auth--rejestracja-i-logowanie)
  - [Messages — wiadomości](#messages--wiadomości)
- [Autoryzacja (JWT)](#autoryzacja-jwt)
- [Testowanie w Swaggerze — krok po kroku](#testowanie-w-swaggerze--krok-po-kroku)
- [Mechanizm synchronizacji (since_id)](#mechanizm-synchronizacji-since_id)
- [Struktura projektu](#struktura-projektu)
- [Znane ograniczenia](#znane-ograniczenia)

---

## Wymagania i instalacja

**Python 3.12**, środowisko wirtualne w `/home/grzeg/BSIUI/`.

```bash
# wejdź do projektu
cd /home/grzeg/BSIUI

# aktywuj venv
source venv/bin/activate

# zainstaluj zależności
pip install fastapi sqlmodel pyjwt "pwdlib[argon2]" python-dotenv python-multipart
```

### Plik `.env`

Utwórz plik `.env` w katalogu projektu:

```env
SECRET_KEY=wpisz-tutaj-dlugi-losowy-ciag-znakow
ALGORITHM=HS256
```

> ⚠️ **Nie commituj `.env` do repozytorium.** Dodaj go do `.gitignore`.

---

## Uruchamianie

```bash
cd /home/grzeg/BSIUI
source venv/bin/activate
fastapi dev app/main.py
```

Serwer startuje na `http://127.0.0.1:8000`.  
Baza danych (`database.db`) tworzona jest automatycznie przy pierwszym uruchomieniu.

| UI | URL |
|---|---|
| **Swagger (interaktywne docs)** | http://127.0.0.1:8000/docs |
| **ReDoc** | http://127.0.0.1:8000/redoc |

---

## Architektura i flow

```
Klient A  ──POST /messages──────────────────────►  Serwer  ──zapisuje──►  SQLite
Klient B  ──GET  /messages/update/{since_id}──►  Serwer  ──zwraca kto pisał──►  Klient B
Klient B  ──GET  /messages/history/{since_id}/{username}──►  historia──►  Klient B
```

- **Serwer jest bezstanowy** — nie „pamięta" klientów. Klient sam trzyma swój `since_id`.
- **Polling** — klient odpytuje `/update` co kilka sekund; przy nowych wiadomościach pobiera `/history`.
- **Historia jest po stronie serwera** — wszystkie wiadomości zostają w bazie na stałe.

---

## Endpointy

### Auth — rejestracja i logowanie

#### `POST /auth/register` — rejestracja

Tworzy nowe konto użytkownika.

**Body (JSON):**
```json
{
  "login": "alice",
  "password": "tajnehaslo123"
}
```

**Odpowiedź `201 Created`:**
```json
{
  "id": 1,
  "username": "alice"
}
```

**Błędy:**
| Kod | Opis |
|-----|------|
| `400` | Użytkownik o tym loginie już istnieje |

---

#### `POST /auth/login` — logowanie, zwraca token JWT

> ⚠️ **Ważne:** Ten endpoint używa formatu **`application/x-www-form-urlencoded`** (formularz), **nie JSON**.  
> W Swaggerze wypełniasz pola `username` i `password` w formularzu.  
> W kodzie klienta ustaw `Content-Type: application/x-www-form-urlencoded`.

**Body (form-data):**
```
username=alice
password=tajnehaslo123
```

**Odpowiedź `200 OK`:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

**Błędy:**
| Kod | Opis |
|-----|------|
| `401` | Zły login lub hasło |

---

### Messages — wiadomości

> 🔒 Wszystkie endpointy `/messages/*` wymagają tokenu JWT w nagłówku:
> ```
> Authorization: Bearer <access_token>
> ```

---

#### `POST /messages` — wyślij wiadomość

**Body (JSON):**
```json
{
  "receiver_name": "bob",
  "msg": "Cześć Bob!"
}
```

**Odpowiedź `201 Created`:**
```json
{
  "id": 42,
  "created_at": "2026-10-28T15:30:00.123456+00:00"
}
```

> 💡 Zapisz zwrócone `id` — możesz go użyć do aktualizacji swojego lokalnego `since_id`.

**Błędy:**
| Kod | Opis |
|-----|------|
| `400` | Pusta wiadomość |
| `400` | Próba napisania do samego siebie |
| `404` | Odbiorca (`receiver_name`) nie istnieje w bazie |
| `401` | Brak/nieprawidłowy token |

---

#### `GET /messages/update/{since_id}` — sprawdź nowe wiadomości

Zwraca **listę nadawców**, którzy wysłali Ci wiadomości po podanym `since_id`.  
Klient używa tego do pollingu — jeśli lista jest pusta, brak nowych wiadomości.

**Parametr ścieżki:**
| Parametr | Typ | Opis |
|----------|-----|------|
| `since_id` | `int` | ID ostatniej wiadomości, którą już masz. Przy pierwszym wywołaniu podaj `0`. |

**Przykład:** `GET /messages/update/0`

**Odpowiedź `200 OK`:**
```json
{
  "senders": [
    {
      "username": "alice",
      "count": 3,
      "last_id": 47
    },
    {
      "username": "charlie",
      "count": 1,
      "last_id": 45
    }
  ]
}
```

| Pole | Opis |
|------|------|
| `username` | Login nadawcy |
| `count` | Liczba nowych wiadomości od tego nadawcy |
| `last_id` | Globalne ID ostatniej wiadomości od tego nadawcy (użyj jako nowego `since_id` przy pobieraniu historii) |

Jeśli brak nowych wiadomości, `senders` jest pustą listą `[]`.

---

#### `GET /messages/history/{since_id}/{receiver_name}` — historia rozmowy

Zwraca historię rozmowy między zalogowanym użytkownikiem a `receiver_name`,  
dla wiadomości o ID **większym niż** `since_id`. Wynik posortowany od najstarszej.

**Parametry ścieżki:**
| Parametr | Typ | Opis |
|----------|-----|------|
| `since_id` | `int` | ID ostatniej pobranej wiadomości. Podaj `0` żeby pobrać całą historię. |
| `receiver_name` | `str` | Login drugiego uczestnika rozmowy |

**Przykład:** `GET /messages/history/0/alice`

**Odpowiedź `200 OK`:**
```json
[
  {
    "id": 1,
    "sender_name": "alice",
    "receiver_name": "bob",
    "msg": "Cześć Bob!",
    "created_at": "2026-10-28T14:00:00+00:00"
  },
  {
    "id": 2,
    "sender_name": "bob",
    "receiver_name": "alice",
    "msg": "Hej Alice!",
    "created_at": "2026-10-28T14:01:00+00:00"
  }
]
```

Przy braku nowych wiadomości zwraca pustą listę `[]`.

**Błędy:**
| Kod | Opis |
|-----|------|
| `404` | Podany `receiver_name` nie istnieje |
| `401` | Brak/nieprawidłowy token |

---

## Autoryzacja (JWT)

Token ważny jest **30 minut**. Po wygaśnięciu należy zalogować się ponownie.

**Nagłówek żądania:**
```http
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

Token podpisany jest kluczem `SECRET_KEY` z `.env`, algorytmem `HS256`.  
Payload tokenu zawiera: `sub` (username) i `exp` (czas wygaśnięcia UTC).

---

## Testowanie w Swaggerze — krok po kroku

### 1. Zarejestruj dwa konta

1. Otwórz http://127.0.0.1:8000/docs
2. Rozwiń `POST /auth/register`
3. Kliknij **Try it out** → wpisz body → **Execute**
4. Powtórz dla drugiego użytkownika (np. `alice` i `bob`)

### 2. Zaloguj się i pobierz token (jako alice)

1. Rozwiń `POST /auth/login`
2. Kliknij **Try it out**
3. Wpisz `username: alice` i `password: ...` w polach formularza (**nie** edytuj JSON)
4. **Execute** → skopiuj wartość `access_token` z odpowiedzi

### 3. Autoryzuj Swaggera

1. Kliknij przycisk **🔒 Authorize** (prawy górny róg strony)
2. W polu **Value** wpisz token (sam token bez słowa `Bearer` — Swagger doda je automatycznie)
3. Kliknij **Authorize** → **Close**

Od teraz wszystkie endpointy będą używać tokenu `alice`.

### 4. Wyślij wiadomość (jako alice → do boba)

```json
POST /messages
{
  "receiver_name": "bob",
  "msg": "Hej Bob, co słychać?"
}
```

Zanotuj zwrócone `id` (np. `1`).

### 5. Zaloguj się jako bob i sprawdź nowe wiadomości

Powtórz krok 2–3 dla konta `bob`. Następnie:

```
GET /messages/update/0
```

Powinieneś zobaczyć `alice` w liście `senders` z `count: 1` i `last_id: 1`.

### 6. Pobierz historię rozmowy (jako bob)

```
GET /messages/history/0/alice
```

Zobaczysz wiadomość od Alice. Następnym razem podaj `since_id = 1`, żeby pobrać tylko nowsze.

---

## Mechanizm synchronizacji (`since_id`)

Serwer jest **bezstanowy** — klient sam zarządza `since_id`.

```
Klient bob — cykl pollingu:

  1. since_id = 0  (na starcie lub po restarcie klienta)

  2. GET /messages/update/{since_id}
     ← {"senders": [{"username": "alice", "count": 2, "last_id": 5}]}

  3. GET /messages/history/{since_id}/alice
     ← [wiadomość id=4, wiadomość id=5]

  4. since_id = 5   ← zapisz DOPIERO po udanym odebraniu historii!

  5. Czekaj N sekund → wróć do kroku 2
```

> ⚠️ **Ważne:** Aktualizuj `since_id` **dopiero po pomyślnym odebraniu** historii z `/history`.  
> Jeśli zaktualizujesz za wcześnie i `/history` się nie powiedzie, utracisz wiadomości.

---

## Struktura projektu

```
BSIUI/
├── .env                    # SECRET_KEY, ALGORITHM (nie commitować!)
├── database.db             # SQLite — tworzona automatycznie
├── README.md
└── app/
    ├── main.py             # Inicjalizacja FastAPI, lifespan, rejestracja routerów
    ├── database.py         # Engine SQLite, SessionDep (dependency injection)
    ├── models.py           # User, Message (tabele) + schematy (UserCreate, MessageRead…)
    ├── security.py         # Hashowanie haseł (argon2), tworzenie/weryfikacja JWT, CurrentUser
    └── routers/
        ├── auth.py         # POST /auth/register, POST /auth/login
        └── texting.py      # POST /messages, GET /messages/update, GET /messages/history
```

---

## Znane ograniczenia

| Ograniczenie | Opis |
|---|---|
| **Brak refresh tokenów** | Po 30 min token wygasa, klient musi zalogować się ponownie |
| **SQLite** | Nie nadaje się do produkcji przy wielu równoczesnych zapisach; wystarczy na potrzeby zajęć |
| **Brak szyfrowania wiadomości** | Treść `msg` przechowywana w bazie jako plain text |
| **Brak paginacji historii** | `/history` zwraca wszystkie wiadomości od `since_id`; przy bardzo długich rozmowach odpowiedź może być duża |
| **Polling, nie WebSocket** | Klient musi sam odpytywać serwer co N sekund |
