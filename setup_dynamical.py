#!/usr/bin/env python3
"""
Dynamical - Criador de Wallpapers Dinâmicos para GNOME
Versão 6.2 - Compatível com GNOME 40+
"""
import gi
import os
import sys
import json
import subprocess
import shutil
import base64
import logging
from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree as ET

# Verificação de dependência Pillow
try:
    from PIL import Image, ImageDraw
    HAS_PIL = True
except ImportError:
    HAS_PIL = False
    print("AVISO: 'Pillow' não encontrado. A pré-visualização não funcionará.")
    print("Instale com: pip install Pillow --break-system-packages")

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

# GTK 3.0
gi.require_version("Gtk", "3.0")
try:
    from gi.repository import Gtk, GLib, Gdk, Gio, GdkPixbuf
except ImportError:
    print("Erro crítico: PyGObject (GTK 3.0) não encontrado.")
    sys.exit(1)

APP_NAME = "Dynamical"
APP_ID   = "com.github.dynamical"

CONFIG_DIR  = Path.home() / ".config"  / "dynamical"
CONFIG_FILE = CONFIG_DIR / "config.json"

DESKTOP_DIR      = Path.home() / ".local" / "share" / "applications"
ICON_DIR         = Path.home() / ".local" / "share" / "icons" / "hicolor" / "48x48" / "apps"
INSTALL_DIR      = Path.home() / ".local" / "bin"
INSTALL_PATH     = INSTALL_DIR / "dynamical.py"

WALLPAPER_BASE_DIR = Path.home() / ".local" / "share" / "backgrounds"
PROPERTIES_DIR     = Path.home() / ".local" / "share" / "gnome-background-properties"

ICON_BASE64 = (
    "PD94bWwgdmVyc2lvbj0iMS4wIiBlbmNvZGluZz0iVVRGLTgiPz4KPHN2ZyB4bWxucz0iaHR0"
    "cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSI0OCIgaGVpZ2h0PSI0OCIgdmlld0Jv"
    "eD0iMCAwIDQ4IDQ4Ij4KIDxkZWZzPgogIDxsaW5lYXJHcmFkaWVudCBpZD0iYSIgeDE9IjAl"
    "IiB5MT0iMCUiIHgyPSIxMDAlIiB5Mj0iMTAwJSI+CiAgIDxzdG9wIG9mZnNldD0iMCUiIHN0"
    "b3AtY29sb3I9IiMzNTg0ZTQiLz4KICAgPHN0b3Agb2Zmc2V0PSIxMDAlIiBzdG9wLWNvbG9y"
    "PSIjMWE1ZmRiIi8+CiAgPC9saW5lYXJHcmFkaWVudD4KIDwvZGVmcz4KIDxjaXJjbGUgY3g9"
    "IjI0IiBjeT0iMjQiIHI9IjIwIiBmaWxsPSJ1cmwoI2EpIi8+CiA8Y2lyY2xlIGN4PSIyNCIg"
    "Y3k9IjI0IiByPSIxMCIgZmlsbD0ibm9uZSIgc3Ryb2tlPSIjZmZmIiBzdHJva2Utd2lkdGg9"
    "IjIiLz4KIDxsaW5lIHgxPSIyNCIgeTE9IjI0IiB4Mj0iMjQiIHkyPSIxOCIgc3Ryb2tlPSIj"
    "ZmZmIiBzdHJva2Utd2lkdGg9IjIiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIvPgogPGxpbmUg"
    "eDE9IjI0IiB5MT0iMjQiIHgyPSIyOCIgeTI9IjI0IiBzdHJva2U9IiNmZmYiIHN0cm9rZS13"
    "aWR0aD0iMiIgc3Ryb2tlLWxpbmVjYXA9InJvdW5kIi8+Cjwvc3ZnPgo="
)

CSS_DATA = b"""
window { background-color: @theme_bg_color; }
.frame-card {
    border: 1px solid @borders;
    border-radius: 12px;
    padding: 15px;
    background-color: @theme_base_color;
    box-shadow: 0 2px 4px rgba(0,0,0,0.05);
}
.preview-container {
    border-radius: 16px;
    border: 1px solid @borders;
    background-color: #000000;
}
button.action-btn {
    border-radius: 8px;
    padding: 5px 12px;
    font-weight: 500;
}
stackswitcher button {
    border-radius: 8px;
    padding: 8px 16px;
    margin: 4px;
}
stackswitcher button:checked {
    background-color: @theme_selected_bg_color;
    color: @theme_selected_fg_color;
}
"""

class ConfigManager:
    DEFAULTS = {
        "collection_name": "MyDynamicWallpaper",
        "wallpapers": {"morning": "", "afternoon": "", "evening": "", "night": ""},
        "times":      {"morning":  6, "afternoon": 12, "evening":    18, "night": 22},
        "enabled":    {"morning": True, "afternoon": True, "evening": True, "night": True},
        "last_folder": str(Path.home()),
        "settings": {
            "transition_time": 30,
            "create_dark_variant": False,
            "dark_wallpapers": {"morning": "", "afternoon": "", "evening": "", "night": ""}
        }
    }

    def __init__(self):
        self.data = {}
        self.load()

    def load(self):
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, "r") as f:
                    loaded = json.load(f)
                self.data = self._deep_merge(
                    json.loads(json.dumps(self.DEFAULTS)), loaded
                )
                return
            except Exception as e:
                logging.warning(f"Config corrompida, usando padrões: {e}")
        self.data = json.loads(json.dumps(self.DEFAULTS))

    def _deep_merge(self, base, override):
        for k, v in override.items():
            if k in base and isinstance(base[k], dict) and isinstance(v, dict):
                base[k] = self._deep_merge(base[k], v)
            else:
                base[k] = v
        return base

    def save(self):
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            with open(CONFIG_FILE, "w") as f:
                json.dump(self.data, f, indent=4)
        except Exception as e:
            logging.error(f"Erro ao salvar config: {e}")


class Installer:
    @staticmethod
    def install():
        try:
            for d in (INSTALL_DIR, WALLPAPER_BASE_DIR, PROPERTIES_DIR,
                      ICON_DIR, DESKTOP_DIR):
                d.mkdir(parents=True, exist_ok=True)

            current = Path(__file__).resolve()
            if current != INSTALL_PATH:
                shutil.copy2(current, INSTALL_PATH)
                os.chmod(INSTALL_PATH, 0o755)

            icon_path = ICON_DIR / f"{APP_ID}.svg"
            with open(icon_path, "wb") as f:
                f.write(base64.b64decode(ICON_BASE64))

            desktop = (
                f"[Desktop Entry]\n"
                f"Version=1.0\n"
                f"Name={APP_NAME}\n"
                f"Comment=Criador de Wallpapers Dinâmicos para GNOME\n"
                f"Exec=python3 {INSTALL_PATH}\n"
                f"Icon={APP_ID}\n"
                f"Terminal=false\n"
                f"Type=Application\n"
                f"Categories=Utility;Settings;GNOME;GTK;\n"
                f"StartupNotify=true\n"
            )
            dp = DESKTOP_DIR / f"{APP_ID}.desktop"
            dp.write_text(desktop)
            os.chmod(dp, 0o755)
            subprocess.run(["update-desktop-database", str(DESKTOP_DIR)],
                           stderr=subprocess.DEVNULL)
            return True
        except Exception as e:
            logging.error(f"Erro na instalação: {e}")
            return False


class WallpaperGenerator:
    """
    Gera XML de wallpaper dinâmico conforme o formato GNOME (gnome-bg/slideshow).

    Regras do formato:
      • <starttime> define o instante T=0 do ciclo, usando uma data fixa no passado.
      • Cada <static> e <transition> empilha duração em segundos de forma LINEAR.
      • A soma de todas as durações deve ser exatamente 86400 s (24 h) para loop perfeito.
      • Não há "wrap-around" implícito: calculamos explicitamente o tempo de 00:00
        até o primeiro evento, o trecho entre eventos, e do último evento até 23:59:59.
    """

    @staticmethod
    def _resolve_image(key: str, dark: bool, cfg: dict) -> str | None:
        """
        Retorna o caminho de imagem para o período/modo pedido.
        Sem fallback cruzado: modo escuro usa só imagens escuras,
        modo claro usa só imagens claras.
        """
        if dark:
            p = cfg["settings"].get("dark_wallpapers", {}).get(key, "")
        else:
            p = cfg["wallpapers"].get(key, "")
        return p if p and Path(p).exists() else None

    @staticmethod
    def _copy_image(src: str, dest_dir: Path, fname: str) -> str:
        """Copia imagem para o diretório de destino e retorna o caminho final."""
        suffix = Path(src).suffix or ".jpg"
        dest = dest_dir / f"{fname}{suffix}"
        if not dest.exists():
            shutil.copy2(src, dest)
        return str(dest)

    @staticmethod
    def _build_xml(cfg: dict, dest_dir: Path, dark: bool) -> Path | None:
        """
        Constrói e salva timed.xml (ou timed-dark.xml).

        Algoritmo correto:
          1. Montar lista de períodos ATIVOS ordenados pela hora (0-23).
          2. Usar hora em segundos para dividir as 86400 s do dia.
          3. Para cada fatia [início, fim):
               a. static  = fatia - transition_secs   (mín. 0)
               b. transition = transition_secs  (de `from` → `to`)
          4. A primeira fatia começa em 00:00 (segundos desde meia-noite).
             O período ativo à meia-noite é o ÚLTIMO da lista ordenada
             (ou o único, se houver só um).
        """
        trans_secs = max(1.0, cfg["settings"].get("transition_time", 30) * 60.0)
        DAY = 86400.0

        # 1. Coletar períodos válidos
        raw = []
        for key in ("morning", "afternoon", "evening", "night"):
            if not cfg["enabled"].get(key, False):
                continue
            path = WallpaperGenerator._resolve_image(key, dark, cfg)
            if not path:
                continue
            hour = int(cfg["times"].get(key, 0)) % 24
            raw.append({"key": key, "hour": hour, "path": path})

        if not raw:
            return None

        # Ordenar por hora (crescente)
        raw.sort(key=lambda x: x["hour"])

        # 2. Copiar imagens para o destino
        file_map = {}
        for p in raw:
            file_map[p["key"]] = WallpaperGenerator._copy_image(
                p["path"], dest_dir, p["key"]
            )

        # 3. Construir lista de fatias cobrindo 86400 s
        #    A fatia começa na hora do evento e termina na hora do próximo.
        #    Rotacionamos para que a fatia que cobre 00:00 seja a primeira.
        n = len(raw)

        # Índice do último período (maior hora) → ativo à meia-noite
        # (porque vai de sua hora até a hora do primeiro do dia seguinte)
        start_idx = n - 1  # índice do período com maior hora

        # Montar sequência rotacionada de pares (current, next)
        slices = []
        for i in range(n):
            curr = raw[(start_idx + i) % n]
            nxt  = raw[(start_idx + i + 1) % n]

            curr_sec = curr["hour"] * 3600.0
            nxt_sec  = nxt["hour"]  * 3600.0

            if i == 0:
                # Fatia que começa em 00:00
                # Duração: de 00:00 até a hora do PRÓXIMO evento
                # Ex.: Noite 22h → Manhã 6h = 6 h
                dur = nxt_sec  # nxt está em horas absolutas
                # Se nxt_sec == 0 (dois eventos à mesma hora) evitar zero
                if dur <= 0:
                    dur = DAY
            else:
                # Fatia normal entre dois eventos consecutivos
                dur = nxt_sec - curr_sec
                if dur <= 0:
                    dur += DAY   # wrap overnight (ex.: 22h→6h = +8h)

            slices.append({
                "from_key": curr["key"],
                "to_key":   nxt["key"],
                "duration": dur,
            })

        # Ajuste fino: garantir que a soma seja exatamente 86400 s
        total = sum(s["duration"] for s in slices)
        if total > 0 and abs(total - DAY) > 0.1:
            factor = DAY / total
            for s in slices:
                s["duration"] *= factor

        # 4. Montar XML
        root = ET.Element("background")

        # starttime: data fixa no passado, hora 00:00:00
        st = ET.SubElement(root, "starttime")
        ET.SubElement(st, "year").text   = "2000"
        ET.SubElement(st, "month").text  = "1"
        ET.SubElement(st, "day").text    = "1"
        ET.SubElement(st, "hour").text   = "0"
        ET.SubElement(st, "minute").text = "0"
        ET.SubElement(st, "second").text = "0"

        for s in slices:
            static_dur = max(0.0, s["duration"] - trans_secs)
            trans_dur  = min(trans_secs, s["duration"])

            if static_dur > 0:
                el = ET.SubElement(root, "static")
                ET.SubElement(el, "duration").text = f"{static_dur:.1f}"
                ET.SubElement(el, "file").text = file_map[s["from_key"]]

            if trans_dur > 0:
                el = ET.SubElement(root, "transition")
                el.set("type", "overlay")
                ET.SubElement(el, "duration").text = f"{trans_dur:.1f}"
                ET.SubElement(el, "from").text = file_map[s["from_key"]]
                ET.SubElement(el, "to").text   = file_map[s["to_key"]]

        fname = "timed-dark.xml" if dark else "timed.xml"
        xml_path = dest_dir / fname
        tree = ET.ElementTree(root)
        if hasattr(ET, "indent"):
            ET.indent(tree, space="  ")
        tree.write(str(xml_path), encoding="UTF-8", xml_declaration=True)
        logging.info(f"XML gerado: {xml_path}")
        return xml_path

    @staticmethod
    def generate(cfg: dict) -> str:
        name = cfg["collection_name"].strip() or "DynamicWallpaper"
        safe = "".join(
            c if c.isalnum() or c in "-_" else "_" for c in name
        ).strip("_") or "DynamicWallpaper"

        # Limpar e recriar diretório
        target = WALLPAPER_BASE_DIR / safe
        if target.exists():
            shutil.rmtree(target)
        target.mkdir(parents=True, exist_ok=True)

        use_dark_variant = cfg["settings"].get("create_dark_variant", False)

        # Tentamos gerar modo claro. Se não tiver imagens claras, xml_light = None.
        xml_light = WallpaperGenerator._build_xml(cfg, target, dark=False)

        xml_dark = None
        if use_dark_variant:
            dark_dir = target / "dark"
            dark_dir.mkdir(exist_ok=True)
            xml_dark = WallpaperGenerator._build_xml(cfg, dark_dir, dark=True)

        # Validação: precisa de pelo menos um XML válido
        if xml_light is None and xml_dark is None:
            raise ValueError(
                "Nenhuma imagem configurada.\n"
                "Selecione pelo menos uma imagem em qualquer período ativo."
            )

        # Se só tem escuro, usa ele também como claro (e vice-versa)
        if xml_light is None:
            xml_light = xml_dark
        if xml_dark is None:
            xml_dark = xml_light

        PROPERTIES_DIR.mkdir(parents=True, exist_ok=True)
        prop_root = ET.Element("wallpapers")
        wp = ET.SubElement(prop_root, "wallpaper")
        wp.set("deleted", "false")
        ET.SubElement(wp, "name").text          = name
        ET.SubElement(wp, "filename").text      = str(xml_light)
        ET.SubElement(wp, "filename-dark").text = str(xml_dark)
        ET.SubElement(wp, "options").text       = "zoom"
        ET.SubElement(wp, "shade_type").text    = "solid"
        ET.SubElement(wp, "pcolor").text        = "#3465a4"
        ET.SubElement(wp, "scolor").text        = "#000000"

        prop_tree = ET.ElementTree(prop_root)
        if hasattr(ET, "indent"):
            ET.indent(prop_tree, space="  ")

        prop_path = PROPERTIES_DIR / f"{safe}.xml"
        prop_tree.write(str(prop_path), encoding="UTF-8", xml_declaration=True)
        logging.info(f"Manifesto gerado: {prop_path}")

        WallpaperGenerator._apply_wallpaper(str(xml_light), str(xml_dark))

        return str(prop_path)

    @staticmethod
    def _apply_wallpaper(uri_light: str, uri_dark: str):
        """
        Aplica o wallpaper dinâmico imediatamente via gsettings,
        sem necessidade de reiniciar a sessão ou abrir Configurações.
        Funciona em GNOME com Wayland e X11.
        """
        # O GNOME aceita caminho absoluto diretamente (sem prefixo file://)
        # para picture-uri / picture-uri-dark
        schema = "org.gnome.desktop.background"
        cmds = [
            ["gsettings", "set", schema, "picture-uri",      uri_light],
            ["gsettings", "set", schema, "picture-uri-dark", uri_dark],
            ["gsettings", "set", schema, "picture-options",  "zoom"],
        ]
        for cmd in cmds:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                logging.warning(f"gsettings falhou: {' '.join(cmd)}\n{result.stderr}")
            else:
                logging.info(f"Aplicado: {' '.join(cmd)}")


class MainWindow(Gtk.ApplicationWindow):
    PERIODS = [
        ("morning",   "Manhã",       "weather-clear"),
        ("afternoon", "Tarde",        "weather-few-clouds"),
        ("evening",   "Entardecer",   "weather-few-clouds-night"),
        ("night",     "Noite",        "weather-clear-night"),
    ]

    def __init__(self, app, config: ConfigManager):
        super().__init__(application=app, title=APP_NAME)
        self.config = config
        self.set_default_size(950, 680)
        self.set_border_width(0)
        self._apply_css()
        self._build_ui()

    def _apply_css(self):
        prov = Gtk.CssProvider()
        prov.load_from_data(CSS_DATA)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(), prov,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def _build_ui(self):
        # HeaderBar
        hb = Gtk.HeaderBar()
        hb.set_show_close_button(True)
        hb.props.title = APP_NAME
        self.set_titlebar(hb)

        btn_gen = Gtk.Button(label="⚡ Gerar e Aplicar")
        btn_gen.get_style_context().add_class("suggested-action")
        btn_gen.connect("clicked", self._on_generate)
        hb.pack_start(btn_gen)

        menu_btn = Gtk.MenuButton()
        menu_btn.set_image(
            Gtk.Image.new_from_icon_name("open-menu-symbolic", Gtk.IconSize.BUTTON)
        )
        builder = Gtk.Builder()
        builder.add_from_string("""
        <interface><menu id='m'><section>
          <item>
            <attribute name='label'>Preferências</attribute>
            <attribute name='action'>app.preferences</attribute>
          </item>
          <item>
            <attribute name='label'>Sobre</attribute>
            <attribute name='action'>app.about</attribute>
          </item>
        </section></menu></interface>
        """)
        menu_btn.set_menu_model(builder.get_object("m"))
        hb.pack_end(menu_btn)

        # Stack principal
        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
        self.add(self.stack)

        self.stack.add_titled(self._build_editor_page(), "editor",  "Editor")
        self.stack.add_titled(self._build_preview_page(), "preview", "Pré-visualização")

        sw = Gtk.StackSwitcher()
        sw.set_stack(self.stack)
        hb.set_custom_title(sw)

    def _build_editor_page(self):
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=15, margin=15)

        # Nome da coleção
        name_frame = Gtk.Frame(label=" Nome da Coleção ")
        name_frame.get_style_context().add_class("frame-card")
        name_inner = Gtk.Box(spacing=10, margin=10)
        self.entry_name = Gtk.Entry(
            text=self.config.data.get("collection_name", ""),
            placeholder_text="Ex: Paisagem Natural"
        )
        name_inner.pack_start(self.entry_name, True, True, 0)
        name_frame.add(name_inner)
        outer.pack_start(name_frame, False, False, 0)

        # Grade de períodos
        grid_frame = Gtk.Frame(label=" Configuração de Períodos ")
        grid_frame.get_style_context().add_class("frame-card")

        grid = Gtk.Grid(column_spacing=15, row_spacing=8, margin=12)
        grid.set_column_homogeneous(False)

        # Cabeçalho
        for col, lbl in enumerate(
            ("Ativo", "Período", "Hora (0-23)", "Imagem Claro", "Imagem Escuro")
        ):
            h = Gtk.Label(label=f"<b>{lbl}</b>", use_markup=True,
                          xalign=0.5, margin_bottom=6)
            grid.attach(h, col, 0, 1, 1)

        self.period_widgets: dict = {}
        create_dark = self.config.data["settings"].get("create_dark_variant", False)

        for row, (key, label, icon_name) in enumerate(self.PERIODS, start=1):
            # Switch ativo
            sw = Gtk.Switch(
                active=self.config.data["enabled"].get(key, True),
                halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER
            )
            sw.connect("state-set", self._on_period_toggle, key)
            grid.attach(sw, 0, row, 1, 1)

            # Ícone + rótulo
            hbox = Gtk.Box(spacing=6, halign=Gtk.Align.START)
            hbox.pack_start(
                Gtk.Image.new_from_icon_name(icon_name, Gtk.IconSize.LARGE_TOOLBAR),
                False, False, 0
            )
            hbox.pack_start(Gtk.Label(label=label, xalign=0), False, False, 0)
            grid.attach(hbox, 1, row, 1, 1)

            # SpinButton hora
            adj = Gtk.Adjustment(
                value=self.config.data["times"].get(key, 0),
                lower=0, upper=23, step_increment=1
            )
            spin = Gtk.SpinButton(adjustment=adj, numeric=True, wrap=True)
            grid.attach(spin, 2, row, 1, 1)

            # Botão imagem claro
            btn_light = Gtk.Button(hexpand=True)
            btn_light.get_style_context().add_class("action-btn")
            self._refresh_btn(
                btn_light,
                self.config.data["wallpapers"].get(key, ""),
                self.config.data["enabled"].get(key, True),
                dark=False
            )
            btn_light.connect("clicked", self._on_file_select, key, False)
            grid.attach(btn_light, 3, row, 1, 1)

            # Botão imagem escuro
            btn_dark = Gtk.Button(hexpand=True)
            btn_dark.get_style_context().add_class("action-btn")
            self._refresh_btn(
                btn_dark,
                self.config.data["settings"].get("dark_wallpapers", {}).get(key, ""),
                self.config.data["enabled"].get(key, True),
                dark=True
            )
            btn_dark.connect("clicked", self._on_file_select, key, True)
            btn_dark.set_no_show_all(True)
            btn_dark.show() if create_dark else btn_dark.hide()
            grid.attach(btn_dark, 4, row, 1, 1)

            self.period_widgets[key] = {
                "sw": sw, "spin": spin,
                "btn_light": btn_light, "btn_dark": btn_dark
            }

        grid_frame.add(grid)
        outer.pack_start(grid_frame, True, True, 0)

        # Toggle modo escuro
        dark_row = Gtk.Box(spacing=8, halign=Gtk.Align.END, margin=8)
        dark_row.pack_start(
            Gtk.Label(label="Ativar coluna Modo Escuro:"), False, False, 0
        )
        self.switch_dark_col = Gtk.Switch(active=create_dark)
        self.switch_dark_col.connect("state-set", self._on_dark_col_toggle)
        dark_row.pack_start(self.switch_dark_col, False, False, 0)
        outer.pack_start(dark_row, False, False, 0)

        return outer

    def _build_preview_page(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, margin=20)

        if not HAS_PIL:
            lbl = Gtk.Label(
                label="⚠ Pillow não instalado. Execute:\n"
                      "pip install Pillow --break-system-packages",
                justify=Gtk.Justification.CENTER
            )
            box.pack_start(lbl, True, True, 0)
            return box

        box.pack_start(
            Gtk.Label(label="<b>Simulação de horário</b>", use_markup=True,
                      xalign=0.0),
            False, False, 0
        )

        self.adj_hour = Gtk.Adjustment(
            value=datetime.now().hour, lower=0, upper=23, step_increment=1
        )
        scale = Gtk.Scale(
            orientation=Gtk.Orientation.HORIZONTAL,
            adjustment=self.adj_hour,
            digits=0, hexpand=True,
            draw_value=True
        )
        scale.connect("value-changed", self._on_preview_update)
        box.pack_start(scale, False, False, 4)

        self.lbl_preview_time = Gtk.Label(
            label=f"Horário simulado: {datetime.now().hour:02d}:00"
        )
        box.pack_start(self.lbl_preview_time, False, False, 0)

        # Container de imagem com crossfade
        self.preview_stack = Gtk.Stack(
            transition_type=Gtk.StackTransitionType.CROSSFADE,
            transition_duration=300
        )
        self.preview_img = [Gtk.Image(), Gtk.Image()]
        self.preview_stack.add_named(self.preview_img[0], "a")
        self.preview_stack.add_named(self.preview_img[1], "b")
        self._preview_side = 0

        frame = Gtk.Frame()
        frame.get_style_context().add_class("preview-container")
        frame.set_size_request(640, 380)
        frame.add(self.preview_stack)
        box.pack_start(frame, True, True, 0)

        # Chave Claro / Escuro
        ctrl = Gtk.Box(spacing=10, halign=Gtk.Align.CENTER, margin=6)
        ctrl.pack_start(Gtk.Label(label="Claro"), False, False, 0)
        self.sw_preview_dark = Gtk.Switch(active=False)
        self.sw_preview_dark.connect("state-set", lambda *_: self._on_preview_update(None))
        ctrl.pack_start(self.sw_preview_dark, False, False, 0)
        ctrl.pack_start(Gtk.Label(label="Escuro"), False, False, 0)
        box.pack_start(ctrl, False, False, 0)

        # Renderizar estado inicial
        GLib.idle_add(self._on_preview_update, None)
        return box

    def _refresh_btn(self, btn: Gtk.Button, path: str, enabled: bool, dark: bool):
        if not enabled:
            btn.set_sensitive(False)
            btn.set_label("—")
            btn.set_tooltip_text("Período desativado")
            return
        btn.set_sensitive(True)
        if path and Path(path).exists():
            btn.set_label(Path(path).name)
            btn.set_tooltip_text(path)
        else:
            btn.set_label("Selecionar imagem…" if not dark else "Usar imagem claro")
            btn.set_tooltip_text("Clique para selecionar uma imagem")

    def _on_dark_col_toggle(self, sw: Gtk.Switch, state: bool):
        self.config.data["settings"]["create_dark_variant"] = state
        for w in self.period_widgets.values():
            w["btn_dark"].show() if state else w["btn_dark"].hide()

    def _on_period_toggle(self, sw: Gtk.Switch, state: bool, key: str):
        w = self.period_widgets[key]
        self._refresh_btn(
            w["btn_light"],
            self.config.data["wallpapers"].get(key, ""),
            state, dark=False
        )
        self._refresh_btn(
            w["btn_dark"],
            self.config.data["settings"].get("dark_wallpapers", {}).get(key, ""),
            state, dark=True
        )

    def _on_file_select(self, btn: Gtk.Button, key: str, dark: bool):
        dlg = Gtk.FileChooserNative.new(
            "Selecionar Imagem", self,
            Gtk.FileChooserAction.OPEN, "_Abrir", "_Cancelar"
        )

        # Pré-selecionar a imagem atual (se existir) para facilitar troca
        if dark:
            current = self.config.data["settings"].get("dark_wallpapers", {}).get(key, "")
        else:
            current = self.config.data["wallpapers"].get(key, "")

        if current and Path(current).exists():
            dlg.set_filename(current)
        else:
            last = self.config.data.get("last_folder", str(Path.home()))
            if Path(last).is_dir():
                dlg.set_current_folder(last)

        ff = Gtk.FileFilter()
        ff.set_name("Imagens (JPEG, PNG, WEBP)")
        for mime in ("image/jpeg", "image/png", "image/webp", "image/gif"):
            ff.add_mime_type(mime)
        dlg.add_filter(ff)

        response = dlg.run()
        if response == Gtk.ResponseType.ACCEPT:
            path = dlg.get_filename()
            self.config.data["last_folder"] = str(Path(path).parent)
            if dark:
                self.config.data["settings"].setdefault("dark_wallpapers", {})[key] = path
            else:
                self.config.data["wallpapers"][key] = path
            self._refresh_btn(btn, path, True, dark)
        # Se cancelou (DISMISS/CANCEL), NÃO toca em nada — label permanece como estava
        dlg.destroy()

    def _on_preview_update(self, _widget):
        if not HAS_PIL:
            return
        hour = int(self.adj_hour.get_value())
        self.lbl_preview_time.set_text(f"Horário simulado: {hour:02d}:00")
        dark = self.sw_preview_dark.get_active()

        # Encontrar imagem ativa – mesma lógica do gerador
        periods = []
        for key, w in self.period_widgets.items():
            if not w["sw"].get_active():
                continue
            path = WallpaperGenerator._resolve_image(key, dark, self.config.data)
            if path:
                periods.append({"hour": int(w["spin"].get_value()), "path": path})
        if not periods:
            return
        periods.sort(key=lambda x: x["hour"])

        # Período ativo: último com hora ≤ hour; se hour < primeiro → último (madrugada)
        active = periods[-1]
        for p in periods:
            if p["hour"] <= hour:
                active = p

        try:
            img = Image.open(active["path"]).convert("RGBA")
            img.thumbnail((640, 380), Image.Resampling.LANCZOS)

            # Máscara arredondada
            mask = Image.new("L", img.size, 0)
            ImageDraw.Draw(mask).rounded_rectangle(
                [(0, 0), img.size], radius=16, fill=255
            )
            img.putalpha(mask)

            raw = img.tobytes()
            w_px, h_px = img.size
            pixbuf = GdkPixbuf.Pixbuf.new_from_bytes(
                GLib.Bytes.new(raw),
                GdkPixbuf.Colorspace.RGB, True, 8,
                w_px, h_px, w_px * 4
            )

            # Crossfade entre as duas imagens do stack
            next_side = 1 - self._preview_side
            self.preview_img[next_side].set_from_pixbuf(pixbuf)
            names = ["a", "b"]
            self.preview_stack.set_visible_child_name(names[next_side])
            self._preview_side = next_side

        except Exception as e:
            logging.error(f"Erro na pré-visualização: {e}")

    def _on_generate(self, _btn):
        # Sincronizar config com widgets
        cfg = self.config.data
        cfg["collection_name"] = self.entry_name.get_text().strip() or "DynamicWallpaper"
        for key, w in self.period_widgets.items():
            cfg["enabled"][key] = w["sw"].get_active()
            cfg["times"][key]   = int(w["spin"].get_value())
        self.config.save()

        try:
            prop_path = WallpaperGenerator.generate(cfg)
            name = cfg["collection_name"]
            dlg = Gtk.MessageDialog(
                transient_for=self,
                flags=Gtk.DialogFlags.MODAL,
                message_type=Gtk.MessageType.INFO,
                buttons=Gtk.ButtonsType.OK,
                text="✅ Wallpaper Dinâmico Criado!"
            )
            dlg.format_secondary_text(
                f"A coleção \"{name}\" foi gerada e aplicada!\n\n"
                "O wallpaper dinâmico já está ativo — "
                "sem necessidade de reiniciar a sessão.\n\n"
                f"Arquivos em:\n{Path(prop_path).parent}"
            )
            dlg.run()
            dlg.destroy()
        except Exception as e:
            logging.error(f"Erro ao gerar: {e}")
            dlg = Gtk.MessageDialog(
                transient_for=self,
                flags=Gtk.DialogFlags.MODAL,
                message_type=Gtk.MessageType.ERROR,
                buttons=Gtk.ButtonsType.OK,
                text="❌ Erro ao gerar wallpaper"
            )
            dlg.format_secondary_text(str(e))
            dlg.run()
            dlg.destroy()


class Application(Gtk.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID,
                         flags=Gio.ApplicationFlags.FLAGS_NONE)
        self.config = ConfigManager()

    def do_startup(self):
        Gtk.Application.do_startup(self)

        # Instalar se necessário
        if not INSTALL_PATH.exists():
            Installer.install()

        # Ações do menu
        for name, cb in (("preferences", self._on_preferences),
                         ("about",       self._on_about)):
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", cb)
            self.add_action(action)

    def do_activate(self):
        win = MainWindow(self, self.config)
        win.show_all()
        win.present()

    def _on_preferences(self, _action, _param):
        win = self.get_active_window()
        dlg = Gtk.Dialog(
            title="Preferências",
            transient_for=win,
            modal=True,
            border_width=15
        )
        dlg.add_button("Cancelar", Gtk.ResponseType.CANCEL)
        dlg.add_button("Salvar",   Gtk.ResponseType.OK)
        dlg.set_default_response(Gtk.ResponseType.OK)

        area = dlg.get_content_area()
        area.set_spacing(8)
        area.pack_start(
            Gtk.Label(label="Tempo de transição entre imagens (minutos):",
                      xalign=0.0),
            False, False, 0
        )
        adj = Gtk.Adjustment(
            value=self.config.data["settings"].get("transition_time", 30),
            lower=1, upper=120, step_increment=1
        )
        spin = Gtk.SpinButton(adjustment=adj, numeric=True)
        area.pack_start(spin, False, False, 0)
        area.show_all()

        if dlg.run() == Gtk.ResponseType.OK:
            self.config.data["settings"]["transition_time"] = int(spin.get_value())
            self.config.save()
        dlg.destroy()

    def _on_about(self, _action, _param):
        dlg = Gtk.AboutDialog(
            transient_for=self.get_active_window(),
            modal=True,
            program_name=APP_NAME,
            version="6.2",
            comments="Criador de Wallpapers Dinâmicos para GNOME",
            website="https://github.com/dynamical",
            license_type=Gtk.License.GPL_3_0,
            authors=["Comunidade Dynamical"],
            logo_icon_name=APP_ID,
        )
        dlg.run()
        dlg.destroy()


def main():
    if "--install" in sys.argv:
        ok = Installer.install()
        print("Instalação concluída." if ok else "Falha na instalação.")
        return

    app = Application()
    try:
        sys.exit(app.run(sys.argv))
    except Exception as e:
        logging.critical(f"Erro fatal: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()