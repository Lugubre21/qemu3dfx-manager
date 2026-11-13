"""Preset hardware per i sistemi guest supportati.

I valori sono scelti per funzionare con i driver gia' inclusi nei sistemi
d'epoca (es. AMD PCnet su Windows 98, Realtek 8139 su XP), cosi' la VM e'
usabile subito dopo l'installazione.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class GuestPreset:
    key: str
    label: str
    ram_mb: int
    disk_gb: int
    cpus: int
    vga: str          # std | cirrus | vmware
    sound: str        # sb16 | ac97 | es1370 | none
    nic: str          # pcnet | rtl8139 | ne2k_pci | e1000 | none
    family: str       # 9x | nt | dos  (decide quali script usa la ISO Tools)
    notes: str = ""


PRESETS: dict[str, GuestPreset] = {
    p.key: p
    for p in (
        GuestPreset(
            "win98", "Windows 98 / 98 SE", 256, 4, 1, "std", "sb16", "pcnet", "9x",
            "Oltre 512 MB di RAM Windows 98 diventa instabile. Per la grafica 2D "
            "in alta risoluzione installa il driver VBE9x/VBEMP.",
        ),
        GuestPreset(
            "winme", "Windows ME", 256, 4, 1, "std", "sb16", "pcnet", "9x",
            "Stesse note di Windows 98.",
        ),
        GuestPreset(
            "win95", "Windows 95", 64, 2, 1, "cirrus", "sb16", "ne2k_pci", "9x",
            "Windows 95 riconosce Cirrus Logic senza driver aggiuntivi.",
        ),
        GuestPreset(
            "win2k", "Windows 2000", 512, 8, 1, "std", "ac97", "rtl8139", "nt",
            "Il driver AC97 va installato a parte.",
        ),
        GuestPreset(
            "winxp", "Windows XP", 1024, 16, 1, "std", "ac97", "rtl8139", "nt",
            "Il driver AC97 (Realtek) va installato a parte.",
        ),
        GuestPreset(
            "dos", "MS-DOS / FreeDOS", 32, 1, 1, "cirrus", "sb16", "none", "dos",
            "I giochi Glide per DOS usano il wrapper GLIDE2X.OVL.",
        ),
    )
}

DEFAULT_PRESET = "win98"

VGA_CHOICES = ["std", "cirrus", "vmware"]
SOUND_CHOICES = ["sb16", "ac97", "es1370", "none"]
NIC_CHOICES = ["pcnet", "rtl8139", "ne2k_pci", "e1000", "none"]


def get_preset(key: str) -> GuestPreset:
    return PRESETS.get(key, PRESETS[DEFAULT_PRESET])
