# formlang: КВ-граматики, рівняння над мовами, лема про накачку, дерева виводу SIPL

[![CI](https://github.com/karaalbina-ship-it/project-tp-sipl/actions/workflows/ci.yml/badge.svg)](https://github.com/karaalbina-ship-it/project-tp-sipl/actions/workflows/ci.yml)

Проєктна робота з курсу «Теорія програмування» (КНУ, ФКНК).
**Автор:** Альбіна Кара, група ТК-32.
**Трек:** «Формальні мови» (практичні роботи 1, 4–6 практикуму Шишацька та ін., 2024).

## Обрані завдання

| ID | Завдання | Бали | Де в коді |
|---|---|---|---|
| FORM-01 | CFG Toolkit: недосяжні/непродуктивні символи, ε-правила, НФ Хомського з поясненням кроків | 2.0 | `src/formlang/transform.py` |
| FORM-02 | Граматика ⇄ система рівнянь над мовами, наближення R(i), порівняння з граматикою | 2.5 | `src/formlang/equations.py`, `words.py` |
| FORM-03 | Pumping Lemma Explorer | 2.0 | `src/formlang/pumping.py` |
| FORM-04 | Derivation Explorer: ліво-/правосторонні виведення, дерева, неоднозначність | 1.5 | `src/formlang/parsing.py`, `render.py` |
| VIS-01 | Дерево синтаксичного виводу SIPL-програми: text/JSON/DOT/SVG із прив'язкою до коду | 1.5 | `src/formlang/sipl.py`, `data/sipl.cfg` |
| REL-01 | CI: ruff + pytest + збірка пакета на кожен push/PR | 0.5 | `.github/workflows/ci.yml` |
| REL-02 | GitHub Release за тегом + SemVer + CHANGELOG | 0.5 | `.github/workflows/release.yml`, розділ «Історія змін» |

Разом заявлено **10.5** бала. Зараховується максимум 10, REL-01 іде як запас.

## Встановлення

Потрібен Python ≥ 3.10. Сторонніх залежностей пакет не має.

```bash
git clone https://github.com/karaalbina-ship-it/project-tp-sipl.git
cd project-tp-sipl
python -m venv .venv
# Windows: .venv\Scripts\activate    Linux/macOS: source .venv/bin/activate
pip install -e ".[dev]"
pytest -q            # тести
ruff check .         # лінтер
```

Після встановлення доступна команда `formlang` (або `python -m formlang`).

## Формат граматики

```text
# коментар; аксіома - ліва частина першого рядка
S -> AbCa | ABB | BScB | aSB
A → Aa | ε
<програма> ::= "begin" <оператор> "end"
```

* `A`, `S0`, `A′`: нетермінали (велика латинська літера, можна зі штрихами або цифрами); `<назва>` теж нетермінал.
* Будь-який інший символ (`a`, `+`, `(`) є однолітерним терміналом. `"begin"` записує термінал із кількох символів.
* `ε` (або `""`) позначає порожній ланцюжок. Пробіли необов'язкові: `AbCa` і `A b C a` означають те саме.

Слово в командному рядку задається посимвольно (`aabb`). Якщо в ньому є пробіли, воно ділиться на токени (`"begin x end"`). Порожнє слово записують як `ε`.

## Команди

### FORM-01: перетворення граматик

```bash
formlang analyze examples/grammars/pr4_example.cfg          # R0, R1, …; Pr0, Pr1, …; ε-нетермінали
formlang reduce  examples/grammars/pr4_example.cfg          # без несуттєвих символів
formlang eps     examples/grammars/pr4_example.cfg --check 6
formlang unit    examples/grammars/pr4_example.cfg
formlang cnf     examples/grammars/pr4_task.cfg --check 6   # НФ Хомського + журнал + перевірка
```

`--check N` порівнює множини слів довжини ≤ N у вихідній і новій граматиці. Для `eps` порівнюється L(G) \ {ε}. Результат для прикладу з практикуму збігається з посібником: `S → AbCa | bCa | ABB | AB | A | BB | B | …`, `A → Aa | a`, `B → bB | b`, `C → Cc | c`.

### FORM-02: системи рівнянь

```text
# examples/equations/pr5_example.eq
S = {c}A
A = {a}A{bbb} ∪ {ε}
```

```bash
formlang equations  examples/grammars/pr5_example.cfg   # граматика → система
formlang to-grammar examples/equations/palindromes.eq   # система → граматика
formlang solve examples/equations/pr5_example.eq --iterations 4 --max-len 9
```

`solve` друкує наближення `R(0) = ∅, R(1) = φ(R(0)), …`, крок стабілізації і порівняння `R(E) ∩ T^≤n` з `L(G) ∩ T^≤n`. Слова граматики знаходить окремий алгоритм: перебір лівих виведень. На вхід можна подати й `.cfg`, тоді система будується з граматики.

### FORM-03: лема про накачку

```bash
formlang pump "a^n b^n c^n" --k-max 6                   # контрприклади для k = 1..6
formlang pump "d b^n a^{3n} e c^{3n} b" --k-max 8 -v    # мова з практичної 6
formlang pump "a^n b^n" --k-max 4                       # КВ-мова: розклади знаходяться
formlang pump "a^n b^n c^n" --decomp "a,a,b,b,cc"       # дослідити конкретний розклад u,t1,x,t2,v
formlang pump --grammar examples/grammars/anbn.cfg --word aaabbb --k 4
```

Шаблон мови записують як `w^{an+b}` з одним параметром `n ≥ --min-n`, наприклад `(ab)^{n+1} c`. Інструмент перебирає всі розклади `t = u·t1·x·t2·v` з `|t1 t2| ≥ 1`, `|t1 x t2| ≤ k` і перевіряє `u·t1^i·x·t2^i·v ∈ L` для `i = 0..max_i`.

> Це **асистент, а не вирішувач**. Перевіряється скінченна кількість `k` та `i`. Знайдений контрприклад лише свідчить, що мова не КВ, і не є доведенням. Розклад, що витримав накачування, не доводить, що мова КВ.

### FORM-04: виведення і дерева

```bash
formlang derive examples/grammars/expr_ambiguous.cfg "a+a*a"            # 2 дерева ⇒ неоднозначна
formlang derive examples/grammars/expr_unambiguous.cfg "a+a*a"          # одне дерево
formlang derive examples/grammars/anbn.cfg aabb --format svg -o t.svg
formlang words  examples/grammars/balanced.cfg --max-len 6
```

`--max-trees K` обмежує кількість дерев, які шукає інструмент. Значення `2` достатньо, щоб виявити неоднозначність. Дерева з циклом `A ⇒⁺ A` на тому самому відрізку слова не розглядаються, бо таких дерев нескінченно багато.

### VIS-01: дерево виводу SIPL-програми

```bash
formlang tree examples/sipl/power.sipl                          # текстове дерево + перевірка листків
formlang tree examples/sipl/power.sipl --format json            # вузли з line/col і фрагментом коду
formlang tree examples/sipl/power.sipl --format svg -o tree.svg
formlang tree examples/sipl/power.sipl --format dot | dot -Tpng -o tree.png
formlang tree examples/sipl/bad_ge.sipl                         # 3:12: неочікуваний токен '='
```

Розбір виконує загальний алгоритм Ерлі за БНФ із практикуму (`src/formlang/data/sipl.cfg`), а не окремий парсер SIPL. Синтаксичну правильність перевіряє обхід листків зліва направо, як у практикумі: він має дати текст програми. БНФ курсу неоднозначна, наприклад `S1; S2; S3` чи `a + b * c`. У таких випадках інструмент попереджає про кілька дерев, а потрібне дерево можна вибрати через `--tree N`.

## JSON і коди завершення

Кожна команда з `--json` (і `tree --format json`) друкує об'єкт `{"schema_version": 1, "command": …, …}`.

| Код | Значення |
|---|---|
| 0 | успіх |
| 1 | слово або програма не належить мові; рівняння й граматика дали різні мови |
| 2 | помилка формату вхідних даних (граматика, система, шаблон, аргументи) |
| 5 | помилка читання або запису файлу |

## Структура

```text
src/formlang/
  grammar.py     модель G = (N, T, P, S), текстовий формат
  parsing.py     алгоритм Ерлі, дерева виводу, ліві/праві виведення
  transform.py   FORM-01
  words.py       перелік слів L(G) довжини ≤ n
  equations.py   FORM-02
  pumping.py     FORM-03
  render.py      текст / JSON / DOT / SVG
  sipl.py        лексер SIPL + VIS-01
  data/sipl.cfg  БНФ SIPL з практикуму
  cli.py         команда formlang
examples/        граматики, системи рівнянь, SIPL-програми
tests/           pytest
```

## Реліз

1. Оновити версію в `pyproject.toml` і `src/formlang/__init__.py`, додати розділ в «Історію змін» нижче.
2. Закомітити зміни й поставити тег, який збігається з версією: `git tag v0.1.0 && git push --tags`.
3. Workflow `Release` перевірить тег, прожене тести, збере `sdist` і `wheel` та створить GitHub Release з нотатками з «Історії змін».

## Обмеження

* Шаблони мов у `pump` мають один параметр `n` і лінійні показники `an+b`.
* У SIPL числа невід'ємні: унарного мінуса в БНФ немає. Також немає `≥`, `<` і коментарів.
* Наближення в `solve` обчислюються лише для слів довжини ≤ `--max-len`. Це точно: конкатенація не вкорочує слова, тож короткі слова результату утворюються лише з коротких слів аргументів.

## Історія змін

Формат версій - [SemVer](https://semver.org/lang/uk/).

### [0.1.0] - 2026-11-19

Додано:
- FORM-01: аналіз КВ-граматики (досяжні Rᵢ, продуктивні Prᵢ, ε-нетермінали), видалення несуттєвих
  символів, ε-правил і ланцюгових правил, нормальна форма Хомського з журналом кроків і перевіркою
  еквівалентності на словах обмеженої довжини (`analyze`, `reduce`, `eps`, `unit`, `cnf --check`).
- FORM-02: системи рівнянь у слабкій алгебрі мов, перетворення граматика ⇄ система, послідовні
  наближення R(i) і порівняння розв'язку з мовою граматики (`equations`, `to-grammar`, `solve`).
- FORM-03: дослідник леми про накачку для мов-шаблонів і мов, заданих граматикою (`pump`).
- FORM-04: алгоритм Ерлі, дерева виводу, ліво-/правосторонні виведення, виявлення
  неоднозначності, перелік слів (`derive`, `words`).
- VIS-01: дерево синтаксичного виводу SIPL-програми за БНФ із практикуму: text/JSON/DOT/SVG,
  прив'язка вузлів до рядків і колонок, перевірка обходом листків (`tree`).
- REL-01/02: GitHub Actions (ruff, pytest, build) і реліз за тегом з артефактами збірки.
