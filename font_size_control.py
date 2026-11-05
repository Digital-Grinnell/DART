"""Runtime font sizing adapted from FLAT for Flet desktop applications.

MIT License

Copyright (c) 2026 Digital.Grinnell / FLAT Contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

import logging
from copy import deepcopy
from dataclasses import fields
from typing import Callable
from weakref import WeakKeyDictionary

import flet as ft


class FontSizeController:
    """Scale page typography and registered text using app-owned persistence."""

    def __init__(
        self,
        page: ft.Page,
        *,
        load_percent: Callable[[], object],
        save_percent: Callable[[str], None],
        logger: logging.Logger | None = None,
    ):
        self.page = page
        self._save_percent = save_percent
        self._logger = logger if logger is not None else logging.getLogger(__name__)
        self._texts: WeakKeyDictionary[ft.Text, float] = WeakKeyDictionary()
        self._text_fields: WeakKeyDictionary[ft.TextField, float] = WeakKeyDictionary()
        self._base_theme = deepcopy(page.theme) if page.theme else ft.Theme()
        self._base_dark_theme = deepcopy(page.dark_theme) if page.dark_theme else ft.Theme()
        saved_percent = load_percent()
        try:
            if not isinstance(saved_percent, (str, int)) or isinstance(saved_percent, bool):
                raise ValueError("expected an integer percentage")
            percent = int(saved_percent)
            if not 75 <= percent <= 200:
                raise ValueError("outside the supported 75%-200% range")
        except (TypeError, ValueError):
            self._logger.warning("Invalid saved font size %r; using 100%%", saved_percent)
            percent = 100
        self._percent = percent

        self._label = ft.Text(f"{percent}%")
        self._smaller = ft.ElevatedButton(
            "A-",
            tooltip="Decrease font size by 10% (minimum 75%)",
            on_click=lambda _: self._set_percent(self._percent - 10),
        )
        self._larger = ft.ElevatedButton(
            "A+",
            tooltip="Increase font size by 10% (maximum 200%)",
            on_click=lambda _: self._set_percent(self._percent + 10),
        )
        self.controls = ft.Row(
            controls=[
                ft.Text("Font size"),
                self._smaller,
                self._label,
                self._larger,
                ft.ElevatedButton(
                    "Reset",
                    tooltip="Reset font size to 100%",
                    on_click=lambda _: self._set_percent(100),
                ),
            ],
            wrap=True,
        )
        self._apply()

    @property
    def percent(self) -> int:
        return self._percent

    def register_text(self, text: ft.Text) -> ft.Text:
        """Register an explicitly sized Text once, using its unscaled size."""
        if text.size is None:
            raise ValueError("register_text requires an explicit Text.size")
        if text not in self._texts:
            self._texts[text] = text.size
        text.size = self._texts[text] * self._percent / 100
        return text

    def sized_text(self, value: str = "", *, size: float | None = None, **kwargs) -> ft.Text:
        """Create themed or explicitly sized text that follows runtime changes."""
        text = ft.Text(value, size=size, **kwargs)
        return self.register_text(text) if size is not None else text

    def sized_text_field(self, *, text_size: float, **kwargs) -> ft.TextField:
        """Include explicitly sized log viewers in the same scaling lifecycle."""
        field = ft.TextField(text_size=text_size * self._percent / 100, **kwargs)
        self._text_fields[field] = text_size
        return field

    def _scaled_theme(self, base: ft.Theme) -> ft.Theme:
        # Flet replaces theme styles rather than merging them. Supply Material 3
        # defaults for missing fields while retaining the app's custom styles.
        typography = {
            # size, line height, letter spacing, weight
            "display_large": (57, 1.12, -0.25, ft.FontWeight.W_400),
            "display_medium": (45, 1.16, 0, ft.FontWeight.W_400),
            "display_small": (36, 1.22, 0, ft.FontWeight.W_400),
            "headline_large": (32, 1.25, 0, ft.FontWeight.W_400),
            "headline_medium": (28, 1.29, 0, ft.FontWeight.W_400),
            "headline_small": (24, 1.33, 0, ft.FontWeight.W_400),
            "title_large": (22, 1.27, 0, ft.FontWeight.W_400),
            "title_medium": (16, 1.50, 0.15, ft.FontWeight.W_500),
            "title_small": (14, 1.43, 0.1, ft.FontWeight.W_500),
            "body_large": (16, 1.50, 0.5, ft.FontWeight.W_400),
            "body_medium": (14, 1.43, 0.25, ft.FontWeight.W_400),
            "body_small": (12, 1.33, 0.4, ft.FontWeight.W_400),
            "label_large": (14, 1.43, 0.1, ft.FontWeight.W_500),
            "label_medium": (12, 1.33, 0.5, ft.FontWeight.W_500),
            "label_small": (11, 1.45, 0.5, ft.FontWeight.W_500),
        }
        theme = deepcopy(base)
        text_theme = ft.TextTheme()
        for name, (size, height, spacing, weight) in typography.items():
            style = ft.TextStyle(
                size=size,
                height=height,
                letter_spacing=spacing,
                weight=weight,
                color=ft.Colors.ON_SURFACE,
            )
            custom = getattr(base.text_theme, name) if base.text_theme else None
            if custom is not None:
                for field in fields(custom):
                    value = getattr(custom, field.name)
                    if value is not None:
                        setattr(style, field.name, deepcopy(value))
            if style.size is not None:
                style.size *= self._percent / 100
            if style.letter_spacing is not None:
                style.letter_spacing *= self._percent / 100
            setattr(text_theme, name, style)
        theme.text_theme = text_theme
        return theme

    def _apply(self) -> None:
        self.page.theme = self._scaled_theme(self._base_theme)
        self.page.dark_theme = self._scaled_theme(self._base_dark_theme)
        for text, base_size in list(self._texts.items()):
            text.size = base_size * self._percent / 100
        for field, base_size in list(self._text_fields.items()):
            field.text_size = base_size * self._percent / 100
        self._label.value = f"{self._percent}%"
        self._smaller.disabled = self._percent == 75
        self._larger.disabled = self._percent == 200

    def _set_percent(self, percent: int) -> None:
        percent = max(75, min(200, percent))
        if percent == self._percent:
            return
        self._save_percent(str(percent))
        self._percent = percent
        self._apply()
        self.page.update()
        self._logger.info("Font size set to %s%%", percent)
