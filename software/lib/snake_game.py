"""Snake game - lazy loaded to save memory at startup."""
import uasyncio as asyncio
import urandom

def create_snake_screen(Screen, oled, wri6, OLED_WIDTH, OLED_HEIGHT,
                        BTN_NEXT, BTN_PREV, BTN_SELECT, BTN_BACK,
                        snake_high_score, save_params, UtilsScreen):
    """Factory function to create SnakeScreen with required dependencies."""

    class SnakeScreen(Screen):
        """
        Snake for 128x64 SSD1306.
        - Grid: 4x4 px cells
        - HUD row at top with boundary line; full border around playfield.
        - Controls:
            NEXT  -> turn right
            PREV  -> turn left
            SELECT-> pause/resume (or restart on game over)
            BACK  -> exit to menu

        NOTE: In ui_task(), do not auto-render when current screen is SnakeScreen.
        """
        CELL = 4
        DIRS = [(1,0), (0,1), (-1,0), (0,-1)]  # R, D, L, U

        def __init__(self, oled):
            super().__init__(oled)

            # ----- GEOMETRY -----
            self.HUD_H = wri6.font.height()
            self.GRID_W = OLED_WIDTH // self.CELL
            self.GRID_H = (OLED_HEIGHT - self.HUD_H) // self.CELL
            self.GRID_Y0 = self.HUD_H

            # Playfield pixel bounds
            self.x_left   = 0
            self.x_right  = self.oled.width - 1
            self.y_top    = self.GRID_Y0
            self.y_bot    = self.GRID_Y0 + self.GRID_H * self.CELL - 1

            # ----- GAME STATE -----
            self.running = True
            self.paused = False
            self.tick_ms_base = 180
            self.tick_ms_min  = 70
            self.tick_ms = self.tick_ms_base
            self.score = 0

            try:
                self.high_score = snake_high_score.value
            except:
                self.high_score = 0

            self.dir_idx = 0  # right
            cx = self.GRID_W // 2
            cy = self.GRID_H // 2
            self.snake = [(cx, cy), (cx-1, cy), (cx-2, cy), (cx-3, cy)]
            self.food = self._rand_empty_cell()
            self.game_over = False

            # Start loop last
            self._task = asyncio.create_task(self._loop())
            self.render()

        # ---------- helpers ----------
        def _cell_free(self, x, y):
            return (x, y) not in self.snake

        def _rand_empty_cell(self):
            for _ in range(200):
                x = urandom.getrandbits(5) % self.GRID_W
                y = urandom.getrandbits(5) % self.GRID_H
                if self._cell_free(x, y):
                    return (x, y)
            for yy in range(self.GRID_H):
                for xx in range(self.GRID_W):
                    if self._cell_free(xx, yy):
                        return (xx, yy)
            return (0, 0)

        def _turn_left(self):
            self.dir_idx = (self.dir_idx - 1) % 4

        def _turn_right(self):
            self.dir_idx = (self.dir_idx + 1) % 4

        def _advance(self):
            dx, dy = self.DIRS[self.dir_idx]
            hx, hy = self.snake[0]
            nx, ny = hx + dx, hy + dy

            # grid-bounds collision
            if nx < 0 or nx >= self.GRID_W or ny < 0 or ny >= self.GRID_H:
                self._end_game()
                return

            # self collision
            if (nx, ny) in self.snake:
                self._end_game()
                return

            # move
            self.snake.insert(0, (nx, ny))

            # eat
            if (nx, ny) == self.food:
                self.score += 1
                self.tick_ms = max(self.tick_ms_min, self.tick_ms_base - self.score * 6)
                self.food = self._rand_empty_cell()
            else:
                self.snake.pop()

        def _end_game(self):
            self.game_over = True
            if self.score > self.high_score:
                self.high_score = self.score
                try:
                    snake_high_score.value = self.high_score
                    save_params()
                except Exception:
                    pass
            self.render()

        async def _loop(self):
            try:
                while self.running:
                    if not self.paused and not self.game_over:
                        self._advance()
                        self.render()
                    await asyncio.sleep_ms(self.tick_ms)
            except asyncio.CancelledError:
                return

        # ---------- drawing ----------
        def _draw_hud(self):
            self.oled.fill_rect(0, 0, self.oled.width, self.HUD_H, 0)
            wri6.set_textpos(self.oled, 0, 0)
            wri6.printstring("SCORE:{:d}".format(self.score))
            hi_txt = "HI:{:d}".format(self.high_score)
            x_hi = self.oled.width - wri6.stringlen(hi_txt)
            wri6.set_textpos(self.oled, 0, x_hi)
            wri6.printstring(hi_txt)
            self.oled.hline(0, self.HUD_H - 1, self.oled.width, 1)

        def render(self):
            self.oled.fill(0)
            self._draw_hud()
            fx, fy = self.food
            self.oled.fill_rect(fx*self.CELL, self.GRID_Y0 + fy*self.CELL, self.CELL, self.CELL, 1)
            for i, (x, y) in enumerate(self.snake):
                px = x * self.CELL
                py = self.GRID_Y0 + y * self.CELL
                if i == 0:
                    self.oled.fill_rect(px, py, self.CELL, self.CELL, 1)
                else:
                    self.oled.rect(px, py, self.CELL, self.CELL, 1)
            if self.paused:
                self._overlay_center("PAUSED")
            elif self.game_over:
                self._overlay_gameover()
            self.oled.vline(self.x_left,  self.y_top, self.y_bot - self.y_top + 1, 1)
            self.oled.vline(self.x_right, self.y_top, self.y_bot - self.y_top + 1, 1)
            self.oled.hline(0, self.y_bot, self.oled.width, 1)
            self.oled.show()

        def _overlay_center(self, text):
            pad = 2
            fh = wri6.font.height()
            max_text_w = self.oled.width - 2 * pad
            if wri6.stringlen(text) > max_text_w:
                base = text
                while base and wri6.stringlen(base + "...") > max_text_w:
                    base = base[:-1]
                text = (base + "...") if base else "..."
            tw = wri6.stringlen(text)
            box_w = min(self.oled.width, tw + 2 * pad)
            box_h = fh + 2 * pad
            x = (self.oled.width - box_w) // 2
            if x < 0: x = 0
            y = self.GRID_Y0 + (self.GRID_H * self.CELL - box_h) // 2
            if y < self.GRID_Y0: y = self.GRID_Y0
            self.oled.fill_rect(x, y, box_w, box_h, 0)
            self.oled.rect(x, y, box_w, box_h, 1)
            tw = wri6.stringlen(text)
            tx = x + (box_w - tw) // 2
            if tx < 0: tx = 0
            wri6.set_textpos(self.oled, y + pad, tx)
            wri6.printstring(text)

        def _overlay_gameover(self):
            lines = ["GAME OVER", "SELECT=Restart"]
            pad = 2
            gap = 1
            fh = wri6.font.height()
            trimmed = []
            for s in lines:
                if wri6.stringlen(s) <= self.oled.width - 2 * pad:
                    trimmed.append(s)
                else:
                    base = s
                    while base and wri6.stringlen(base + "...") > self.oled.width - 2 * pad:
                        base = base[:-1]
                    trimmed.append((base + "...") if base else "...")
            lines = trimmed
            max_line_w = max(wri6.stringlen(s) for s in lines)
            box_w = min(self.oled.width, max_line_w + 2 * pad)
            box_h = 2 * fh + gap + 2 * pad
            x = (self.oled.width - box_w) // 2
            if x < 0: x = 0
            y = self.GRID_Y0 + (self.GRID_H * self.CELL - box_h) // 2
            if y < self.GRID_Y0: y = self.GRID_Y0
            self.oled.fill_rect(x, y, box_w, box_h, 0)
            self.oled.rect(x, y, box_w, box_h, 1)
            ty = y + pad
            for s in lines:
                tw = wri6.stringlen(s)
                tx = x + (box_w - tw) // 2
                if tx < 0: tx = 0
                wri6.set_textpos(self.oled, ty, tx)
                wri6.printstring(s)
                ty += fh + gap

        # ---------- input ----------
        async def handle_button(self, btn):
            if not self.game_over and not self.paused:
                if btn == BTN_NEXT:
                    self._turn_right()
                elif btn == BTN_PREV:
                    self._turn_left()
            if btn == BTN_SELECT:
                if self.game_over:
                    try:
                        if self._task:
                            self._task.cancel()
                            await asyncio.sleep_ms(0)
                    except Exception:
                        pass
                    self.__init__(self.oled)
                    return self
                else:
                    self.paused = not self.paused
                    self.render()
                    return self
            if btn == BTN_BACK:
                self.running = False
                try:
                    if self._task:
                        self._task.cancel()
                except Exception:
                    pass
                return UtilsScreen(self.oled)
            return self

    return SnakeScreen(oled)