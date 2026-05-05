/**
 * Political and legal term glossary — EN / HE / RU.
 * (AGENTS.MD Phase 8 — consistent translation of politically sensitive terms)
 *
 * Usage:
 *   import { glossary } from "@/locales/glossary";
 *   glossary.knesset.en  // "Knesset"
 *   glossary.knesset.he  // "כנסת"
 *   glossary.knesset.ru  // "Кнессет"
 *
 * Do NOT use machine translation for new entries.
 * Hebrew and Russian entries require native-speaker review before public release.
 */

export interface GlossaryEntry {
  en: string;
  he: string;
  ru: string;
  /** Short factual definition in English (required) */
  definition_en: string;
}

export type GlossaryKey =
  | "knesset"
  | "mk"
  | "basic_law"
  | "supreme_court"
  | "judicial_review"
  | "override_clause"
  | "coalition"
  | "opposition"
  | "electoral_threshold"
  | "plenum_vote"
  | "bill"
  | "haredi"
  | "shabbat"
  | "kashrut"
  | "two_state_solution"
  | "settlements"
  | "attorney_general"
  | "proportional_representation"
  | "confidence_vote"
  | "political_brand";

export type Glossary = Record<GlossaryKey, GlossaryEntry>;

export const glossary: Glossary = {
  knesset: {
    en: "Knesset",
    he: "כנסת",
    ru: "Кнессет",
    definition_en: "The unicameral national legislature of Israel, comprising 120 members.",
  },
  mk: {
    en: "MK (Member of Knesset)",
    he: "חבר כנסת (ח\"כ)",
    ru: "Депутат Кнессета",
    definition_en: "An elected member of the Israeli parliament (Knesset).",
  },
  basic_law: {
    en: "Basic Law",
    he: "חוק יסוד",
    ru: "Основной закон",
    definition_en:
      "A constitutional-level law in Israel. Israel has no formal constitution; Basic Laws serve as its functional equivalent.",
  },
  supreme_court: {
    en: "Supreme Court",
    he: "בית המשפט העליון",
    ru: "Верховный суд",
    definition_en:
      "The highest court in Israel, which also functions as the High Court of Justice (Bagatz) for administrative and constitutional matters.",
  },
  judicial_review: {
    en: "Judicial review",
    he: "ביקורת שיפוטית",
    ru: "Судебный контроль",
    definition_en:
      "The power of courts to strike down laws or government actions that conflict with constitutional norms.",
  },
  override_clause: {
    en: "Override clause",
    he: "פסקת ההתגברות",
    ru: "Преодолевающая оговорка",
    definition_en:
      "A proposed provision that would allow the Knesset to re-enact laws struck down by the Supreme Court.",
  },
  coalition: {
    en: "Coalition",
    he: "קואליציה",
    ru: "Коалиция",
    definition_en:
      "A governing alliance of parties holding at least 61 of the 120 Knesset seats.",
  },
  opposition: {
    en: "Opposition",
    he: "אופוזיציה",
    ru: "Оппозиция",
    definition_en: "Parties in the Knesset that are not part of the governing coalition.",
  },
  electoral_threshold: {
    en: "Electoral threshold",
    he: "אחוז הבלֶם",
    ru: "Избирательный порог",
    definition_en:
      "The minimum percentage of votes (3.25% in Israel) a party must receive to enter the Knesset.",
  },
  plenum_vote: {
    en: "Plenary vote",
    he: "הצבעה במליאה",
    ru: "Пленарное голосование",
    definition_en:
      "A vote held by all Knesset members in the full chamber (as opposed to committee votes).",
  },
  bill: {
    en: "Bill",
    he: "הצעת חוק",
    ru: "Законопроект",
    definition_en: "A proposal for a new law submitted to the Knesset for consideration.",
  },
  haredi: {
    en: "Haredi (ultra-Orthodox)",
    he: "חרדי",
    ru: "Харедим (ультраортодоксы)",
    definition_en:
      "Strictly observant Orthodox Jewish community in Israel, associated with parties such as UTJ and Shas.",
  },
  shabbat: {
    en: "Shabbat (Sabbath)",
    he: "שבת",
    ru: "Шаббат (Суббота)",
    definition_en:
      "The Jewish day of rest from Friday sunset to Saturday night. Commerce and public transport are restricted by law in many Israeli cities.",
  },
  kashrut: {
    en: "Kashrut (kosher dietary law)",
    he: "כשרות",
    ru: "Кашрут (законы кошерности)",
    definition_en:
      "Jewish dietary laws governing permitted and forbidden foods. The state currently holds a monopoly on kosher certification.",
  },
  two_state_solution: {
    en: "Two-state solution",
    he: "פתרון שתי המדינות",
    ru: "Решение о двух государствах",
    definition_en:
      "A proposed framework for Israeli-Palestinian peace involving two independent states — Israel and Palestine — living side by side.",
  },
  settlements: {
    en: "Settlements",
    he: "התנחלויות",
    ru: "Поселения",
    definition_en:
      "Israeli civilian communities built in the West Bank (Judea and Samaria) since 1967. Their legal status is disputed internationally.",
  },
  attorney_general: {
    en: "Attorney General",
    he: "היועץ המשפטי לממשלה",
    ru: "Генеральный прокурор (Юридический советник правительства)",
    definition_en:
      "Israel's top legal official who advises the government and can block certain executive actions. Independence from the government is a key reform debate.",
  },
  proportional_representation: {
    en: "Proportional representation",
    he: "ייצוג יחסי",
    ru: "Пропорциональное представительство",
    definition_en:
      "Israel's electoral system where parties receive seats in proportion to their share of the national vote.",
  },
  confidence_vote: {
    en: "Vote of no-confidence",
    he: "הצבעת אי-אמון",
    ru: "Голосование о вотуме недоверия",
    definition_en:
      "A Knesset vote that, if passed by 61 members, can bring down the government.",
  },
  political_brand: {
    en: "Political brand",
    he: "מותג פוליטי",
    ru: "Политический бренд",
    definition_en:
      "A long-lived political identity that may persist across party name changes, splits, and mergers (SmartVoter concept).",
  },
};

/** Return the localized label for a term slug. Falls back to English. */
export function termLabel(
  key: GlossaryKey,
  lang: "en" | "he" | "ru"
): string {
  return glossary[key]?.[lang] ?? glossary[key]?.en ?? key;
}

