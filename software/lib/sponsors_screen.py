"""Sponsors screen - lazy loaded to save memory at startup."""
import sys
import os

def create_sponsors_screen(Screen, oled, BTN_NEXT, BTN_PREV, BTN_BACK, UtilsScreen):
    """Factory function to create SponsorsScreen with required dependencies."""

    class SponsorsScreen(Screen):
        def __init__(self, oled):
            super().__init__(oled)

            # Import logos dynamically
            LOGO_FOLDER = "logos"
            if LOGO_FOLDER not in sys.path:
                sys.path.append(LOGO_FOLDER)
            logo_files = sorted([f for f in os.listdir(LOGO_FOLDER) if f.endswith(".py")])

            self.logos = []
            self.current_logo = 0
            for f in logo_files:
                module_name = f[:-3]  # strip '.py'
                mod = __import__(module_name)
                if hasattr(mod, "fb"):
                    self.logos.append(mod.fb)
                else:
                    print(f"Warning: {module_name} has no attribute 'fb'")

            if not self.logos:
                raise RuntimeError("No valid logos found!")

        def render(self):
            self.oled.fill(0)
            self.oled.blit(self.logos[self.current_logo], 0, 0)
            self.oled.show()

        async def handle_button(self, btn):
            if btn == BTN_NEXT:
                self.current_logo = (self.current_logo + 1) % len(self.logos)
            elif btn == BTN_PREV:
                self.current_logo = (self.current_logo - 1) % len(self.logos)
            if btn == BTN_BACK:
                return UtilsScreen(self.oled)
            return self

    return SponsorsScreen(oled)