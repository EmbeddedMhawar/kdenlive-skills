#!/usr/bin/env python3
"""
fetch_official_minecraft_sfx.py

Fetches official, authentic Minecraft sound assets directly from Mojang's CDN
(resources.download.minecraft.net) and converts them to standard 48kHz 16-bit WAV.

Covers:
- Eating & Drinking: eat_bite, eating (full crunch sequence), burp, drink
- Combat & Damage: classic_oof, hit_damage, fall_damage, crit_hit, shield_block, totem_pop, bow_shoot, bow_hit
- Actions & World: splash, tnt_fuse, tnt_explode, chest_open, chest_close, door_open, door_close, anvil_impact, anvil_break, item_break, glass_break, fizz, flint_and_steel, bell_ding
- UI & Items: orb_pickup, level_up, pop, click, wood_click
- Mobs: creeper_hiss, villager_huh, villager_yes, villager_no, villager_trade, zombie_groan, enderman_teleport, enderman_stare, ghast_screech, ghast_fireball, cow_moo, sheep_baa
"""

import os
import shutil
import subprocess
import tempfile
import urllib.request
from pathlib import Path

TARGET_DIR = Path(__file__).resolve().parent.parent / "resources" / "sfx" / "minecraft"

# Hash map of Mojang CDN assets
MINECRAFT_ASSETS = {
    # Eating & Drinking
    "eat_bite": "ebf6fcfa3dd26d6f684fd90388221d4ee4a1af1d",      # random/eat1.ogg
    "eat_2": "608792c62e053a9ddf9fc3bd493a6da1437ad36a",         # random/eat2.ogg
    "eat_3": "d8a23d7672a2e277c8a0c08e131fded629fb5db7",         # random/eat3.ogg
    "burp": "389e837fa8c7f8f09499b43d8710489dfd8c53dd",          # random/burp.ogg
    "drink": "ed402bb1c240a70fa9eb05fe5eec436c248598f2",         # random/drink.ogg

    # Combat & Damage
    "classic_oof": "9d485556b89bf776042080774679c37300bc744b",   # random/classic_hurt.ogg (Original OOF)
    "hit_damage": "c43077ac1f9ceda7e9e1c152f839baf207833aa8",    # damage/hit1.ogg
    "fall_damage": "6582e589d649de71649f01db4f24eb8d90ea0a74",   # damage/fallbig.ogg
    "crit_hit": "caa8f5d2de3c3fa53eca358967e930a45cafca18",      # entity/player/attack/crit1.ogg
    "shield_block": "f3b8dcde479d572a5c6973d5b73314eecd785dd6",  # item/shield/block1.ogg
    "totem_pop": "f3fa2f7ac95f0bd8419b9638b2e6b289265e4b18",     # item/totem/use_totem.ogg
    "bow_shoot": "4a6c47aa4f8c2cfe3237b250ed19b8714d611fd2",     # random/bow.ogg
    "bow_hit": "8648a8dcbe82c047b60d74783f7b1c9eb5826290",       # random/bowhit1.ogg

    # UI & Items
    "orb_pickup": "8a04a60d5c28fc60df472a877ca57f37eabc78d7",    # random/orb.ogg
    "level_up": "19034765ba8ba5389b35804ab213537ab5cf706f",      # random/levelup.ogg
    "pop": "d6ae1c04d0a7376a33d1df12e1b8057cfbab6bc2",           # random/pop.ogg
    "click": "3455ca942556c7d5eac7dd5e458e7fb3bad564c9",         # random/click.ogg
    "wood_click": "cb7fd9405357f21decb5de0b373b837dadcbca9c",    # random/wood_click.ogg

    # Actions & World
    "anvil_impact": "781d4bfc6ee0aff2a61b0d78f0da34610a28aa62",  # random/anvil_land.ogg
    "anvil_break": "6fa4895a44f671fd7c24c366f87ca908da6485a3",   # random/anvil_break.ogg
    "item_break": "8abcbed843fff26146330dde170862e64b8491ab",    # random/break.ogg
    "glass_break": "fa35a51bb74a4a6cf0c48161342db5a8577f13e5",   # random/glass1.ogg
    "splash": "ceddbe3cb01ed6f356d455a1960d13d96afb5363",        # random/splash.ogg
    "fizz": "bd76df5c882dc4b65925a8b25c0e7dbebef9bb2e",          # random/fizz.ogg
    "chest_open": "186d5d9481d59cc99bc4be1b5fbb98d0ef877b8e",    # random/chestopen.ogg
    "chest_close": "056393a33a9633685c3dc3be2887f5cbd7dbc63f",   # random/chestclosed.ogg
    "door_open": "5bb5a04e776d69ca12b1d7bc369975f9bf62e741",     # random/door_open.ogg
    "door_close": "9ea8a9e105321891bda18b9007b383b40aa7c076",    # random/door_close.ogg
    "tnt_fuse": "b9a550ba1e028c027557572aeb928b760864efe4",      # random/fuse.ogg
    "tnt_explode": "fa85b9e7e54c36c9f9d0249ca739444b5e3bb66c",   # random/explode1.ogg
    "flint_and_steel": "f125c13e6b445091cd1efd409547ffb9452138f5",# fire/ignite.ogg
    "bell_ding": "af7fdeee060b5618460246826695c45b17fdbe3f",     # block/bell/bell_use01.ogg

    # Mobs
    "creeper_hiss": "6fc976d65fc742451db2049a2a38a1007b976bc1",  # mob/creeper/say1.ogg
    "villager_huh": "fd2a15ba3147d954e840e76bffe5ffdd89a07a51",  # mob/villager/idle1.ogg
    "villager_yes": "284933d50341876997cbc95b64864b6abab113af",  # mob/villager/yes1.ogg
    "villager_no": "323c80e65c321928f08ca320b1f8eb4b95acfa3b",   # mob/villager/no1.ogg
    "villager_trade": "5aeb216fb57aee98f9f6b1dca27cf22c259586c1",# mob/villager/haggle1.ogg
    "zombie_groan": "65b762da90c8b192ee065692fcd50068f571b3fc",  # mob/zombie/say1.ogg
    "enderman_teleport": "15eb7f0940b43b5422524c8f20db44b72b310233", # mob/endermen/portal.ogg
    "enderman_stare": "75b6933acfef6d24e2205b01f34d8907c5fb9dad", # mob/endermen/stare.ogg
    "ghast_screech": "b846fade34b2a51499e24134c5c0536bb8c4d49b", # mob/ghast/scream1.ogg
    "ghast_fireball": "3066a05ff74bb537d38e2172c257f28f1b3f6e53",# mob/ghast/charge.ogg
    "cow_moo": "50b928af4d33822d8cc5ca0d0161053e491b6c5a",       # mob/cow/say1.ogg
    "sheep_baa": "debbd3aa0f42c073f44313d4d8e5b6dccf3b55fa",     # mob/sheep/say1.ogg
}


def download_and_convert(name: str, file_hash: str, tmp_dir: Path, target_dir: Path) -> Path:
    prefix = file_hash[:2]
    url = f"https://resources.download.minecraft.net/{prefix}/{file_hash}"
    ogg_path = tmp_dir / f"{name}.ogg"
    wav_path = target_dir / f"{name}.wav"

    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=10) as resp, open(ogg_path, "wb") as out_f:
        shutil.copyfileobj(resp, out_f)

    # Convert to 48kHz 16-bit mono WAV with ffmpeg
    subprocess.run([
        "ffmpeg", "-y", "-i", str(ogg_path),
        "-ar", "48000", "-ac", "1",
        str(wav_path)
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    return wav_path


def create_full_eating_sequence(target_dir: Path, tmp_dir: Path):
    """Concatenate eat_bite, eat_2, eat_3, eat_bite into an authentic eating sequence."""
    eat1 = target_dir / "eat_bite.wav"
    eat2 = target_dir / "eat_2.wav"
    eat3 = target_dir / "eat_3.wav"
    out_eating = target_dir / "eating.wav"

    # Concat list file
    list_file = tmp_dir / "eat_concat.txt"
    with open(list_file, "w") as f:
        f.write(f"file '{eat1.resolve()}'\n")
        f.write(f"file '{eat2.resolve()}'\n")
        f.write(f"file '{eat3.resolve()}'\n")
        f.write(f"file '{eat1.resolve()}'\n")
        f.write(f"file '{eat2.resolve()}'\n")

    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", str(list_file),
        "-ar", "48000", "-ac", "1",
        str(out_eating)
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print("Created composite: eating.wav (full eating crunch sequence)")


def main():
    TARGET_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp_dir_str:
        tmp_dir = Path(tmp_dir_str)
        print(f"Downloading {len(MINECRAFT_ASSETS)} official Minecraft sound effects from Mojang CDN...")

        for name, file_hash in MINECRAFT_ASSETS.items():
            wav = download_and_convert(name, file_hash, tmp_dir, TARGET_DIR)
            print(f"  [OK] {wav.name}")

        create_full_eating_sequence(TARGET_DIR, tmp_dir)

    print(f"\nAll official Minecraft sound effects successfully downloaded and converted in:\n{TARGET_DIR}")


if __name__ == "__main__":
    main()
