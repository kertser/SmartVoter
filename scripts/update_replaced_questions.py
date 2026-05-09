"""
One-time migration: replace old question texts with the new de-duplicated versions.

Run with:
    uv run python scripts/update_replaced_questions.py

This updates only the 8 questions that were rewritten to eliminate duplicate
coverage of the same policy axis across different policy items:
  - eco_02 Q1 (child benefits → elderly care)
  - eco_03 Q1/Q2 (rent caps/public housing → developer tax / affordable quota)
  - rel_03 Q1/Q2 (Haredi service → religion-state legal exemption framing)
  - mil_01 Q1/Q2 (Haredi exemptions → universal service / conscientious objector)

Matching is done by policy item slug + approximate old English text.
If a question is no longer found in the DB (already updated or never seeded),
the row is skipped safely.
"""
import sys
from pathlib import Path

# Make sure backend package is importable
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.app.db.session import SessionLocal
from backend.app.models.question import Question
from backend.app.models.policy_item import PolicyItem

# ------------------------------------------------------------------
# Mapping: (old_text_snippet, new_en, new_he, new_ru)
# old_text_snippet is a unique substring of the old English question text
# ------------------------------------------------------------------
REPLACEMENTS = [
    # eco_02 Q1: child benefits → elderly care
    (
        "Should the state expand child benefits and social assistance programs",
        "Should the state significantly increase funding for elderly care and nursing home support to ensure dignified aging for all citizens?",
        "האם על המדינה להגדיל משמעותית את המימון לטיפול בקשישים ולבתי אבות כדי להבטיח זקנה בכבוד לכל האזרחים?",
        "Должно ли государство значительно увеличить финансирование ухода за пожилыми людьми и домов престарелых, чтобы обеспечить достойное старение для всех граждан?",
    ),
    # eco_03 Q1: rent caps → multi-property surtax
    (
        "Should the government intervene to cap residential rental prices",
        "Should owners of multiple investment properties pay a progressive surtax to discourage speculative hoarding of residential units?",
        "האם בעלי דירות מרובות להשקעה צריכים לשלם מס נוסף פרוגרסיבי כדי להגביל ספסרות בדירות מגורים?",
        "Должны ли владельцы нескольких инвестиционных объектов платить прогрессивный дополнительный налог, чтобы препятствовать спекулятивному скоплению жилых единиц?",
    ),
    # eco_03 Q2: public housing → affordable unit quota
    (
        "Should the state build and rent public housing at subsidized rates",
        "Should private developers be legally required to include a minimum quota of affordable or subsidised units in every new residential project?",
        "האם יש לחייב יזמים פרטיים בחוק לכלול מכסה מינימלית של יחידות דיור בהישג יד בכל פרויקט מגורים חדש?",
        "Должны ли застройщики быть обязаны по закону включать минимальную долю доступного или субсидируемого жилья в каждый новый жилой проект?",
    ),
    # rel_03 Q1: "Should ultra-Orthodox (Haredi) men be required to serve in the Israeli military?"
    (
        "Should ultra-Orthodox (Haredi) men be required to serve in the Israeli military",
        "Should religious institutions such as yeshivas have any legally recognised authority to exempt their students from civic obligations imposed by the state, including military conscription?",
        "האם למוסדות דתיים כמו ישיבות צריכה להיות סמכות מוכרת בחוק לפטור את תלמידיהם מחובות אזרחיות שהמדינה מטילה, לרבות גיוס לצבא?",
        "Должны ли религиозные учреждения, такие как иешивы, иметь законодательно признанные полномочия освобождать своих учеников от гражданских обязательств, введённых государством, включая военный призыв?",
    ),
    # rel_03 Q2: "Should Haredi men who study full-time in yeshivas receive a formal exemption from military service?"
    (
        "Should Haredi men who study full-time in yeshivas receive a formal exemption from military service",
        "Should Israeli law explicitly guarantee that Torah study in a state-recognised yeshiva constitutes a protected religious right that cannot be overridden by military conscription orders?",
        "האם החוק הישראלי צריך לקבוע במפורש כי לימוד תורה בישיבה מוכרת על ידי המדינה הוא זכות דתית מוגנת שאינה יכולה להיבטל על ידי צווי גיוס?",
        "Должен ли израильский закон прямо гарантировать, что изучение Торы в государственно признанной иешиве является защищённым религиозным правом, которое не может быть отменено приказами о призыве на военную службу?",
    ),
    # mil_01 Q1: "Should military service be truly universal, applying equally to ultra-Orthodox and Arab citizens?"
    (
        "Should military service be truly universal, applying equally to ultra-Orthodox and Arab citizens",
        "Should Israel establish a mandatory national service framework that applies equally to all citizens — Jewish, Arab, and Druze — regardless of religion or ethnicity, with civilian service tracks available as an alternative to combat?",
        "האם ישראל צריכה להקים מסגרת שירות לאומי חובה החלה באופן שווה על כל האזרחים — יהודים, ערבים ודרוזים — ללא קשר לדת או לאום, כשמסלולים אזרחיים יהיו חלופה לשירות קרבי?",
        "Должен ли Израиль создать систему обязательной национальной службы, которая в равной мере распространяется на всех граждан — евреев, арабов и друзов — вне зависимости от религии или национальности, с гражданскими альтернативными треками вместо боевой службы?",
    ),
    # mil_01 Q2: "Should ultra-Orthodox students enrolled in full-time Torah study continue to receive military service exemptions?"
    (
        "Should ultra-Orthodox students enrolled in full-time Torah study continue to receive military service exemptions",
        "Should individuals who have conscientious or religious objections to bearing arms be allowed to fulfil their national obligation through extended civilian community service rather than military service?",
        "האם אנשים בעלי התנגדות מצפונית או דתית לשאת נשק צריכים להיות רשאים למלא את חובתם הלאומית באמצעות שירות קהילתי אזרחי ממושך במקום שירות צבאי?",
        "Должны ли лица, имеющие принципиальные или религиозные возражения против ношения оружия, иметь право выполнять свой национальный долг через длительную гражданскую общественную службу вместо военной?",
    ),
]


def main() -> None:
    db = SessionLocal()
    try:
        updated = 0
        skipped = 0

        for old_snippet, new_en, new_he, new_ru in REPLACEMENTS:
            # Find the question by a unique substring of its old English text
            matches = (
                db.query(Question)
                .filter(Question.question_text_en.contains(old_snippet))
                .all()
            )
            if not matches:
                print(f"SKIP (not found): {old_snippet[:70]}...")
                skipped += 1
                continue

            for q in matches:
                q.question_text_en = new_en
                q.question_text_he = new_he
                q.question_text_ru = new_ru
                updated += 1
                print(f"  UPDATE [{q.id}]: {new_en[:80]}...")

        db.commit()
        print(f"\nDone. Updated: {updated}, Skipped: {skipped}")
    except Exception as exc:
        db.rollback()
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()

