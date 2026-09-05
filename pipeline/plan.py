"""Pick today's product + scene and write the Bulgarian copy.

Copy is written by the model (guarded by the ULLE brand-facts whitelist) when
OPENAI_API_KEY is set, and falls back to a curated on-brand bank otherwise, so
the pipeline never hard-fails on the copy step.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import random
import urllib.error
import urllib.request

from . import common, prompt as prompt_mod

# On-brand fallback lines — refined, sensory, premium. Short parallel clauses about
# fabric and cut. (headline, accent, subhead). `accent` must be a substring of headline.
FALLBACK_LINES = [
    ("Памук, нежен на допир. Кройка, прилягаща перфектно.", "нежен на допир", "100% памук сингъл 240 гр · Пловдив"),
    ("Плат, който усещаш. Кройка, която стои.", "който усещаш", "Оувърсайз, изпипана след ~15 проби"),
    ("Мек памук, чиста линия.", "чиста линия", "240 гр сингъл · собствен цех в Пловдив"),
    ("Тежината на истинския памук.", "истинския памук", "240 грама, плътна и матова"),
    ("Изчистена кройка, безупречен памук.", "безупречен памук", "100% памук · ситопечат, не лепенка"),
    ("Нежен на допир, плътен на вид.", "Нежен на допир", "Сингъл 240 гр · държи форма пране след пране"),
    ("Памук с тегло и характер.", "тегло и характер", "240 гр · произведено в Пловдив"),
    ("Кройка, която ляга точно.", "ляга точно", "Оувърсайз след ~15 проби · Пловдив"),
    ("Меко отвън, устойчиво във времето.", "устойчиво", "Плътен памук, който държи форма"),
    ("Лято в чист памук.", "чист памук", "100% памук сингъл 240 гр · Юлле, Пловдив"),
]

BRAND_SYSTEM = (
    "Ти си копирайтърът на ULLE (Юлле) — български бранд оувърсайз тениски от Пловдив. "
    "Тонът е изчистен, сетивен и премиум - като бутикова марка, която говори тихо и уверено. "
    "Наблягаш на усещането: допирът на плата, тежината на памука, как ляга кройката. "
    "Елегантно, спокойно, без възклицания и без нахаканост.\n"
    "Реални факти: 100% памук сингъл 240 гр (плътна, мека, не прозира, държи форма); собствен "
    "цех в Пловдив; висококачествен ситопечат, част с надувен 3D ефект; бродерия и тъкан "
    "етикет; оувърсайз кройка, изпипана след ~15 проби.\n\n"
    "СТИЛ: Пиши САМО на български. Кратко заглавие, за предпочитане две паралелни части, "
    "разделени с точка или запетая - едната за плата, другата за кройката/усещането "
    "(напр. „Памук, нежен на допир. Кройка, прилягаща перфектно.“). Меки, точни прилагателни. "
    "Използвай истинско доказателство за плата и кройката, не общи приказки. "
    "Тире пиши САМО като обикновено „-“; никога дълго „—“ или средно „–“.\n"
    "ЗАБРАНЕНО (клише/AI/евтино): „качество на достъпна цена“, „изрази себе си“, „усети "
    "разликата“, „не просто дреха, а начин на живот“, „комфорт и стил“, „за всеки повод“, "
    "възклицателни знаци, емоджи в заглавието, ГЛАВНИ букви за наблягане, нахакан или "
    "шеговит тон. Никакви измислени факти, отстъпки или цени извън подадените.\n"
    "Примери за ДОБРО: „Памук, нежен на допир. Кройка, прилягаща перфектно.“ · „Мек памук, "
    "чиста линия.“ · „Тежината на истинския памук.“\n"
    "Примери за ЛОШО (не пиши така): „Изрази себе си с ULLE!“ · „Премиум качество на "
    "достъпна цена“ · „Памук, който усещаш с пръсти“ (твърде разговорно)."
)


def _openai_chat(model: str, product: dict, offer: str, cta: str, link: str,
                 max_chars: int) -> dict | None:
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        return None
    user = (
        f"Продукт: {product['name']} (щампа: {product.get('print','')}, цена {product.get('price','')}). "
        f"Оферта: {offer}. CTA: {cta}. Линк: {link}. "
        f"Върни СТРИКТНО JSON с ключове: headline (до {max_chars} знака, ударно, без точка накрая), "
        f"accent (една дума или кратка фраза, която ТОЧНО се съдържа в headline — най-силната дума, "
        f"ще се набие с друг шрифт), post_title (заглавие на самия пост — кратка кука за първия ред на "
        f"описанието, различна от headline, до 60 знака, може 1 емоджи), subhead (кратко, до 40 знака), "
        f"caption (2-4 изречения за описанието на поста, може 1-2 емоджи), hashtags (списък от 5-8 "
        f"български/брандови хаштага без #)."
    )
    body = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": BRAND_SYSTEM},
            {"role": "user", "content": user},
        ],
        "temperature": 0.9,
        "response_format": {"type": "json_object"},
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions", data=body,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        content = payload["choices"][0]["message"]["content"]
        data = json.loads(content)
        if not data.get("headline"):
            return None
        return data
    except (urllib.error.URLError, KeyError, json.JSONDecodeError, IndexError) as exc:
        common.log("copy_fallback", reason=str(exc)[:120])
        return None


# Which scenes fit which theme, so the background matches the message.
SCENE_BY_THEME = {
    # calm, warm, reassuring — a clear zone for a message
    "announcement": ["golden_hour_backlight", "cafe_bokeh", "low_angle_sky", "palm_shadow_wall"],
    # bold, energetic — an offer should pop
    "evergreen": ["poolside_caustics", "palm_shadow_wall", "wind_on_line", "diagonal_flatlay", "low_angle_sky"],
    # tactile / premium — sells the fabric and cut
    "product": ["macro_puff", "palm_shadow_wall", "golden_hour_backlight", "cafe_bokeh", "wind_on_line", "diagonal_flatlay"],
}


def _scene_for_theme(cfg: dict, theme_type: str, seed: int) -> str:
    allowed = cfg.get("scenes", [])
    cand = [s for s in SCENE_BY_THEME.get(theme_type, allowed) if s in allowed] or allowed
    return common.pick(cand, seed)


def _product_copy(cfg: dict, product: dict, seed: int) -> dict:
    """Product-theme copy: model-written (guarded) or the curated fallback bank."""
    if cfg.get("copy", {}).get("source") == "agent":
        offers_text = "; ".join(o["headline"].rstrip(".") for o in cfg.get("offers", [])) \
            or cfg.get("offer", "")
        copy = _openai_chat(
            cfg["copy"].get("model", "gpt-4o-mini"), product,
            offers_text, cfg.get("cta", ""), cfg.get("link", ""),
            cfg["copy"].get("max_headline_chars", 52),
        )
        if copy:
            return copy
    h, accent, sub = common.pick(FALLBACK_LINES, seed)
    return {
        "headline": h, "accent": accent,
        "post_title": h, "subhead": sub,
        "caption": f"{h} {sub}. {cfg.get('offer','')} - {cfg.get('cta','')}.",
        "hashtags": ["ulle", "юлле", "българскимарки", "оувърсайз",
                     "памук", "изберибългарското", "пловдив"],
    }


def _active_announcements(cfg: dict) -> list[dict]:
    """User-authored announcements active today. The bot formats these; it never
    invents them — factual messages (delays, deadlines, sales) come only from here."""
    path = common.ROOT / cfg.get("announcements_file", "announcements.json")
    if not path.exists():
        return []
    try:
        items = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        common.log("announcements_bad_json", reason=str(exc)[:120])
        return []
    today = common.today(cfg)
    active = []
    for it in items:
        if not it.get("text"):
            continue
        start = it.get("start")
        end = it.get("end")
        try:
            if start and _dt.date.fromisoformat(start) > today:
                continue
            if end and _dt.date.fromisoformat(end) < today:
                continue
        except ValueError:
            pass
        active.append(it)
    return active


def _copy_from_announcement(ann: dict, cfg: dict) -> dict:
    return {
        "headline": ann["text"],
        "accent": ann.get("accent"),
        "post_title": ann.get("post_title") or "Съобщение от Юлле 💛",
        "subhead": ann.get("subhead", ""),
        "badge": ann.get("badge", ""),
        "caption": ann.get("caption") or f"{ann['text']} {ann.get('subhead','')}".strip(),
        "hashtags": ann.get("hashtags", ["ulle", "юлле", "пловдив"]),
    }


def _evergreen_copy(cfg: dict, seed: int) -> dict:
    # Standing, always-true promos (from config.offers) + brand truths. Safe to auto-post.
    sub_default = "100% памук сингъл 240 гр · цех в Пловдив"
    bank: list[tuple[str, str, str, str]] = []
    for off in cfg.get("offers", []):
        bank.append((off["headline"], off.get("accent", ""), sub_default, off.get("badge", "Оферта")))
    bank += [
        ("Шито в нашия цех в Пловдив.", "в Пловдив", "100% памук сингъл 240 гр", ""),
        ("100% памук. Нищо друго.", "100% памук", "Сингъл 240 гр · оувърсайз кройка", ""),
        ("Направено в България, с внимание.", "в България", "Собствен цех в Пловдив", ""),
    ]
    h, accent, sub, badge = common.pick(bank, seed)
    return {
        "headline": h, "accent": accent, "post_title": h.rstrip("."),
        "subhead": sub, "badge": badge,
        "caption": f"{h} {sub}.".strip(),
        "hashtags": ["ulle", "юлле", "българскимарки", "пловдив", "изберибългарското"],
    }


def make_plan(cfg: dict, n: int = 1) -> dict:
    common.load_env()
    seed = common.date_seed(cfg, salt=f"plan-{n}")
    product = common.pick_weighted(cfg["products"], seed)

    # Priority 1: an active user-authored announcement (never invented).
    announcements = _active_announcements(cfg)
    theme_type = "product"
    layout = "full"
    cta = cfg.get("cta", "")
    copy = None

    if announcements:
        ann = common.pick(announcements, seed)
        theme_type = "announcement"
        copy = _copy_from_announcement(ann, cfg)
        cta = ann.get("cta", "")
    else:
        themes = cfg.get("themes", [{"key": "product", "type": "product", "weight": 1}])
        theme = common.pick_weighted(themes, common.date_seed(cfg, salt=f"theme-{n}"))
        theme_type = theme.get("type", "product")
        if theme_type == "evergreen":
            copy = _evergreen_copy(cfg, seed)
        else:
            theme_type = "product"
            copy = _product_copy(cfg, product, seed)

    copy = common.clean_copy(copy)  # force plain hyphens, never — or –

    # The scene is chosen to match the theme, so background and message agree.
    scene_key = _scene_for_theme(cfg, theme_type, common.date_seed(cfg, salt=f"scene-{theme_type}-{n}"))
    date_str = common.today(cfg).strftime("%Y-%m")
    bg_prompt = prompt_mod.build(product, scene_key, n=n, date_str=date_str)

    return {
        "id": common.post_id(cfg, n),
        "date": common.today(cfg).isoformat(),
        "theme": theme_type,
        "layout": layout,
        "product": product,
        "scene": scene_key,
        "copy": copy,
        "offer": cfg.get("offer", ""),
        "cta": cta,
        "link": cfg.get("link", ""),
        "product_url": product.get("product_url") or product.get("landing", ""),
        "platforms": cfg.get("platforms", []),
        "bg_prompt": bg_prompt,
        "text_zone": bg_prompt["text_zone"],
    }
