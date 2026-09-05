"""Build a shirt-in-scene image prompt for a chosen scene.

Full-generative with the reference photo: the model generates the scene around the
real shirt and must keep the shirt identical. The lock language below is as strong
as we can make it; combined with input_fidelity=high it keeps the print/label close,
though fine text can still drift a little (accepted trade-off).
"""
from __future__ import annotations

# The strongest "do not touch the garment" instruction we can give the model.
LOCK = (
    "CRITICAL: The t-shirt in the attached reference image must be reproduced EXACTLY, "
    "pixel-faithful - do NOT redraw, restyle, recolour, re-letter or reinterpret it. "
    "Keep the chest print {P} with the identical letters, colours, smiley and brush "
    "strokes; keep the small woven label and its text and the ULLE logo exactly as they "
    "are; keep the sleeve embroidery, the ribbed neck and the oversized fit identical. "
    "Change ONLY the environment around the shirt, never the shirt itself."
)

SCENES: dict[str, dict] = {
    "palm_shadow_wall": {
        "bg": "Твърда палмова сянка по стената, силно слънце",
        "type": "plovdiv_wall",
        "env": ("The shirt hangs on a thin matte-black hanger against a warm terracotta-white concrete "
                "wall in strong afternoon sun, with hard-edged palm-frond shadows raking across the wall "
                "around it. High contrast, cinematic. The upper wall is clean and smooth."),
        "tone": "mid-light", "text_color": "deep charcoal #20201E",
        "zone": "top_band", "region": "0,0 -> 1080,430", "cov": 32,
    },
    "wind_on_line": {
        "bg": "Дълбоко синьо небе, морски бриз",
        "type": "seaside",
        "env": ("The shirt is clipped to a thin clothesline against a deep saturated blue summer sky with "
                "a few crisp clouds low and to the sides; the hem lifts gently in the breeze while the "
                "printed chest stays flat to camera. Warm rim light. The upper sky is open and clean."),
        "tone": "dark", "text_color": "soft white #F5F1E8",
        "zone": "top_band", "region": "0,0 -> 1080,470", "cov": 35,
    },
    "poolside_caustics": {
        "bg": "Басейн, водни отблясъци",
        "type": "poolside",
        "env": ("The shirt lies flat on glossy turquoise pool tile seen from above, bright rippling water "
                "caustics dancing across the wet tile around it, deep cyan shadows, crisp specular sparkle. "
                "The lower band of tile is calmer and evenly lit."),
        "tone": "mid-dark", "text_color": "soft white #F5F1E8",
        "zone": "bottom_band", "region": "0,900 -> 1080,1350", "cov": 33,
    },
    "golden_hour_backlight": {
        "bg": "Златен час, топъл контражур",
        "type": "golden_hour",
        "env": ("The shirt hangs on an invisible mannequin with a low golden sun behind it, warm rim light "
                "around the edges, soft lens flare and dust motes in the beam, a blurred warm amber field "
                "behind. Dreamy and premium. The foreground sits in soft even shade."),
        "tone": "dark", "text_color": "warm cream #F5F1E8",
        "zone": "bottom_band", "region": "0,900 -> 1080,1350", "cov": 33,
    },
    "diagonal_flatlay": {
        "bg": "Теракота плочки, диагонални сенки",
        "type": "flatlay",
        "env": ("The shirt lies flat, print facing up, on a sun-warmed terracotta tile surface seen from "
                "above, hard directional light casting a crisp diagonal shadow of an olive branch across "
                "the tile. Warm, graphic. The right side of the frame is open, evenly-lit tile."),
        "tone": "light", "text_color": "deep charcoal #20201E",
        "zone": "right_column", "region": "620,0 -> 1080,1350", "cov": 38,
    },
    "low_angle_sky": {
        "bg": "Нисък ъгъл срещу голямо небе",
        "type": "low_angle",
        "env": ("The shirt is on an invisible mannequin on a pale stone plinth, shot from a low hero angle "
                "against a huge dramatic sky - warm gold near the horizon shifting to deep blue above, a "
                "few sculptural clouds. Warm sidelight. The vast open sky fills the top of the frame."),
        "tone": "dark", "text_color": "soft white #F5F1E8",
        "zone": "top_band", "region": "0,0 -> 1080,470", "cov": 35,
    },
    "cafe_bokeh": {
        "bg": "Кафене в Капана, топло боке",
        "type": "cafe_table",
        "env": ("The shirt is folded on a warm wooden cafe table, with a rich warm bokeh of a Plovdiv "
                "old-town street behind - soft string lights and greenery, no readable signs. The "
                "foreground shirt is sharp; the world behind is alive but softly out of focus."),
        "tone": "dark", "text_color": "warm cream #F5F1E8",
        "zone": "top_band", "region": "0,0 -> 1080,440", "cov": 33,
    },
    "macro_puff": {
        "bg": "Мека фактурна повърхност, режеща светлина",
        "type": "textured_surface",
        "env": ("The shirt lies on a soft neutral textured surface - warm linen or fine sand - with hard "
                "raking light skimming across, revealing the cotton texture and casting a long gentle "
                "shadow. Minimal, tactile, premium. The lower area falls into soft even shade."),
        "tone": "dark", "text_color": "soft white #F5F1E8",
        "zone": "bottom_band", "region": "0,930 -> 1080,1350", "cov": 30,
    },
}


def build(product: dict, scene_key: str, n: int = 1, date_str: str = "") -> dict:
    s = SCENES[scene_key]
    P = product.get("print", product["name"])
    prompt_string = (
        f"Realistic photograph, 4:5 vertical, striking and cinematic. {LOCK.format(P=P)} "
        f"{s['env']} The heavy 100% cotton keeps its real folds and the print bends with them. "
        f"The image is completely text-free apart from the {P} print and the small label already on "
        f"the shirt - no captions, headlines, logos or watermarks added anywhere."
    )
    return {
        "id": f"ulle-bg-{date_str}-{scene_key}-{n:02d}",
        "meta": {
            "brand": "ULLE / Юлле", "product": product["name"],
            "concept_bg": s["bg"], "scene_type": s["type"],
            "engine": "gpt-image-1", "mode": "full_generative", "language": "bg",
        },
        "output": {"aspect_ratio": "4:5", "resolution": "1080x1350", "format": "png"},
        "reference": {
            "product_image": product["reference_image"],
            "preserve": ["chest print", "woven label + ULLE logo", "sleeve embroidery",
                         "white colourway", "oversized fit"],
            "may_change": "scene, framing, lighting only - never the garment",
        },
        "scene": {"summary": s["bg"], "setting": s["type"], "mood": "лято, енергия"},
        "text_zone": {
            "position": s["zone"], "region_px": s["region"], "tone": s["tone"],
            "recommended_text_color": s["text_color"], "coverage_pct": s["cov"],
            "notes": "kept calm for readable overlay text",
        },
        "negative_prompt": ("changing the shirt, redrawing the print, altering the logo or label, "
                            "extra text, captions, added logos, watermark, people, low quality"),
        "prompt_string": prompt_string,
    }
