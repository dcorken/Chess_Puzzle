"""Pawn = Queen: a 4x4 sliding chess puzzle.

Get the red pawn to the red square at the bottom-left using ordinary chess moves.
No captures. The pawn becomes a queen when it reaches the top row.

Run with:  python3 chess_puzzle.py   (requires pygame: pip install pygame)
"""

import math
import random
import sys
from array import array

import pygame

from puzzle_logic import (
    BISHOP, FORBIDDEN, KNIGHT, PAWN, QUEEN, ROOK, SIZE, TARGET,
    apply_move, is_legal_move, is_solved, starting_board,
)

# ---------------------------------------------------------------- layout
SQUARE = 120
FRAME = 22                      # wooden border around the squares
BOARD_PX = SQUARE * SIZE
MARGIN_X = 70
TOP = 90
WIDTH = BOARD_PX + 2 * (MARGIN_X + FRAME)
HEIGHT = TOP + BOARD_PX + 2 * FRAME + 110
BOARD_LEFT = MARGIN_X + FRAME
BOARD_TOP = TOP + FRAME

# ---------------------------------------------------------------- colours
BACKGROUND = (92, 64, 44)
FRAME_COLOUR = (120, 66, 36)
FRAME_EDGE = (74, 38, 20)
LIGHT_SQ = (222, 184, 135)
DARK_SQ = (181, 136, 90)
TARGET_SQ = (178, 44, 40)
PLAQUE = (214, 170, 110)
PLAQUE_TEXT = (92, 50, 24)
SELECT = (255, 222, 60, 150)
WHITE_PIECE = (246, 244, 238)
RED_PIECE = (196, 48, 38)
OUTLINE = (40, 30, 24)
TEXT = (250, 240, 225)
BUTTON = (160, 92, 48)
BUTTON_HOVER = (190, 115, 62)
POWER_UP_FLASH = [(255, 255, 255), (255, 215, 60), RED_PIECE, (255, 140, 30)]
POWER_UP_MS = 1100              # length of the promotion animation (matches the sound)

GLYPHS = {PAWN: "♟", ROOK: "♜", BISHOP: "♝", KNIGHT: "♞", QUEEN: "♛"}


# ---------------------------------------------------------------- sounds
def _tone(freqs, duration, volume=0.4, wave="sine", rate=44100):
    """Build a pygame Sound from a list of frequencies played one after another."""
    samples = array("h")
    per_note = int(rate * duration)
    for freq in freqs:
        for i in range(per_note):
            t = i / rate
            phase = math.sin(2 * math.pi * freq * t)
            value = (1.0 if phase >= 0 else -1.0) if wave == "square" else phase
            envelope = min(1.0, i / 400) * (1 - i / per_note)   # quick attack, linear fade
            samples.append(int(32767 * volume * envelope * value))
    channels = pygame.mixer.get_init()[2]
    if channels == 2:
        stereo = array("h")
        for s in samples:
            stereo.extend((s, s))
        samples = stereo
    return pygame.mixer.Sound(buffer=samples.tobytes())


def _power_up_notes():
    """Rapid rising major arpeggios, like a classic video-game power-up."""
    notes = []
    for step in range(12):
        root = 262 * 2 ** (step * 2 / 12)       # climb a whole tone each cycle
        notes += [root, root * 1.26, root * 1.5]
    return notes


class Sounds:
    def __init__(self):
        self.enabled = False
        try:
            pygame.mixer.init(frequency=44100, size=-16, channels=2)
            self.error = _tone([150, 110], 0.12, volume=0.25, wave="square")
            self.move = _tone([660], 0.05, volume=0.15)
            self.power_up = _tone(_power_up_notes(), 0.03, volume=0.18, wave="square")
            self.win = _tone([523, 659, 784, 1047, 784, 1047], 0.13, volume=0.3)
            self.enabled = True
        except pygame.error:
            print("Sound unavailable - continuing without audio.")

    def play(self, name):
        if self.enabled:
            getattr(self, name).play()


# ---------------------------------------------------------------- celebration
class Confetti:
    COLOURS = [(255, 80, 80), (255, 200, 40), (80, 200, 120), (80, 160, 255), (220, 110, 255), (255, 255, 255)]

    def __init__(self, x, y, burst=False):
        self.x, self.y = x, y
        if burst:
            angle = random.uniform(0, 2 * math.pi)
            speed = random.uniform(3, 11)
            self.vx, self.vy = math.cos(angle) * speed, math.sin(angle) * speed - 4
        else:
            self.vx, self.vy = random.uniform(-1.5, 1.5), random.uniform(1, 4)
        self.size = random.randint(5, 10)
        self.colour = random.choice(self.COLOURS)
        self.spin = random.uniform(0, 2 * math.pi)
        self.spin_speed = random.uniform(0.1, 0.3)

    def update(self):
        self.vy = min(self.vy + 0.18, 6)
        self.vx *= 0.99
        self.x += self.vx + math.sin(self.spin) * 0.8
        self.y += self.vy
        self.spin += self.spin_speed

    def draw(self, surface):
        w = max(1, int(abs(math.cos(self.spin)) * self.size))
        pygame.draw.rect(surface, self.colour, (self.x - w / 2, self.y - self.size / 2, w, self.size))


# ---------------------------------------------------------------- game
class Game:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Pawn = Queen")
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        self.clock = pygame.time.Clock()
        self.sounds = Sounds()

        self.piece_font = pygame.font.Font(pygame.font.match_font("applesymbols,segoeuisymbol,dejavusans"), 96)
        self.use_glyphs = self.piece_font.size(GLYPHS[KNIGHT])[0] > 20
        if not self.use_glyphs:     # font has no chess symbols - fall back to letters
            self.piece_font = pygame.font.SysFont("arial", 64, bold=True)
        self.title_font = pygame.font.SysFont("georgia", 38, bold=True)
        self.text_font = pygame.font.SysFont("georgia", 20)
        self.plaque_font = pygame.font.SysFont("georgia", 26, bold=True)
        self.small_plaque_font = pygame.font.SysFont("georgia", 14, italic=True)
        self.banner_font = pygame.font.SysFont("georgia", 56, bold=True)

        self.piece_images = {}
        self.reset_rect = pygame.Rect(0, 0, 160, 50)
        self.reset_rect.center = (WIDTH // 2, HEIGHT - 45)
        self.reset()

    # ------------------------------------------------------------ state
    def reset(self):
        self.board = starting_board()
        self.selected = None
        self.won = False
        self.win_time = 0
        self.confetti = []
        self.shake = 0              # frames of shake left on an illegal move
        self.shake_square = None
        self.power_up_square = None  # square of a pawn currently transforming into a queen
        self.power_up_start = 0

    # ------------------------------------------------------------ coordinates
    @staticmethod
    def square_rect(square):
        row, col = square
        return pygame.Rect(BOARD_LEFT + col * SQUARE, BOARD_TOP + (SIZE - 1 - row) * SQUARE, SQUARE, SQUARE)

    @staticmethod
    def square_at(pos):
        x, y = pos[0] - BOARD_LEFT, pos[1] - BOARD_TOP
        if 0 <= x < BOARD_PX and 0 <= y < BOARD_PX:
            return (SIZE - 1 - y // SQUARE, x // SQUARE)
        return None

    # ------------------------------------------------------------ input
    def handle_click(self, pos):
        if self.reset_rect.collidepoint(pos):
            self.reset()
            return
        if self.won or self.power_up_square is not None:
            return
        square = self.square_at(pos)
        if square is None:
            return

        if square in self.board:
            # Clicking a piece: select it, deselect it, or switch selection to it.
            self.selected = None if square == self.selected else square
        elif self.selected is not None:
            # Clicking an empty (or forbidden) square with a piece selected: try to move there.
            if is_legal_move(self.board, self.selected, square):
                promoted = apply_move(self.board, self.selected, square)
                self.selected = None
                if promoted:
                    self.power_up_square = square
                    self.power_up_start = pygame.time.get_ticks()
                    self.sounds.play("power_up")
                elif is_solved(self.board):
                    self.celebrate()
                else:
                    self.sounds.play("move")
            else:
                self.sounds.play("error")
                self.shake = 14
                self.shake_square = self.selected

    def celebrate(self):
        self.won = True
        self.win_time = pygame.time.get_ticks()
        self.sounds.play("win")
        cx, cy = self.square_rect(TARGET).center
        self.confetti = [Confetti(cx, cy, burst=True) for _ in range(160)]

    # ------------------------------------------------------------ drawing
    def piece_image(self, piece, colour=None):
        """Render (and cache) a piece glyph: filled colour with a dark outline."""
        if colour is None:
            colour = RED_PIECE if piece in (PAWN, QUEEN) else WHITE_PIECE
        if (piece, colour) not in self.piece_images:
            text = GLYPHS[piece] if self.use_glyphs else piece
            fill = self.piece_font.render(text, True, colour)
            edge = self.piece_font.render(text, True, OUTLINE)
            w, h = fill.get_size()
            image = pygame.Surface((w + 6, h + 6), pygame.SRCALPHA)
            for dx in (-3, -2, 0, 2, 3):
                for dy in (-3, -2, 0, 2, 3):
                    if dx or dy:
                        image.blit(edge, (3 + dx, 3 + dy))
            image.blit(fill, (3, 3))
            self.piece_images[piece, colour] = image
        return self.piece_images[piece, colour]

    def draw_board(self):
        frame = pygame.Rect(MARGIN_X, TOP, BOARD_PX + 2 * FRAME, BOARD_PX + 2 * FRAME)
        pygame.draw.rect(self.screen, FRAME_COLOUR, frame, border_radius=10)
        pygame.draw.rect(self.screen, FRAME_EDGE, frame, 3, border_radius=10)

        for row in range(SIZE):
            for col in range(SIZE):
                square = (row, col)
                if square in FORBIDDEN:
                    continue
                colour = TARGET_SQ if square == TARGET else (DARK_SQ if (row + col) % 2 == 0 else LIGHT_SQ)
                pygame.draw.rect(self.screen, colour, self.square_rect(square))

        # Forbidden squares are covered by an engraved plaque, as on the real puzzle.
        plaque = self.square_rect((0, 1)).union(self.square_rect((0, 2))).inflate(-6, -6)
        pygame.draw.rect(self.screen, PLAQUE, plaque, border_radius=6)
        pygame.draw.rect(self.screen, PLAQUE_TEXT, plaque, 2, border_radius=6)
        title = self.plaque_font.render("PAWN = QUEEN", True, PLAQUE_TEXT)
        self.screen.blit(title, title.get_rect(center=(plaque.centerx, plaque.top + 32)))
        for i, line in enumerate(["Use the standard chess movements", "to get the Pawn to the red square"]):
            text = self.small_plaque_font.render(line, True, PLAQUE_TEXT)
            self.screen.blit(text, text.get_rect(center=(plaque.centerx, plaque.top + 64 + i * 20)))

        if self.selected is not None:
            overlay = pygame.Surface((SQUARE, SQUARE), pygame.SRCALPHA)
            overlay.fill(SELECT)
            self.screen.blit(overlay, self.square_rect(self.selected))

    def draw_pieces(self):
        for square, piece in self.board.items():
            rect = self.square_rect(square)
            if self.shake and square == self.shake_square:
                rect = rect.move(int(math.sin(self.shake * 1.6) * 6), 0)
            if square == self.power_up_square:
                continue
            image = self.piece_image(piece)
            self.screen.blit(image, image.get_rect(center=(rect.centerx, rect.centery + 4)))
        if self.power_up_square is not None:
            self.draw_power_up(self.square_rect(self.power_up_square))

    def draw_power_up(self, rect):
        """Classic power-up flash: the piece flickers between pawn and queen in cycling colours."""
        elapsed = pygame.time.get_ticks() - self.power_up_start
        if elapsed >= POWER_UP_MS:
            self.power_up_square = None
            self.screen.blit(self.piece_image(QUEEN), self.piece_image(QUEEN).get_rect(center=(rect.centerx, rect.centery + 4)))
            return

        frame = elapsed // 60
        progress = elapsed / POWER_UP_MS

        # Flashing square background and expanding rings of light.
        if frame % 2 == 0:
            glow = pygame.Surface(rect.size, pygame.SRCALPHA)
            glow.fill((255, 250, 200, 150))
            self.screen.blit(glow, rect)
        for offset in (0, 0.33, 0.66):
            ring = (progress * 2 + offset) % 1
            radius = int(20 + ring * SQUARE * 0.7)
            pygame.draw.circle(self.screen, (255, 230, 90), rect.center, radius, max(1, int(6 * (1 - ring))))

        # Early on the pawn dominates; the queen appears more and more often until it takes over.
        show_queen = (frame % 3 != 0) if progress > 0.5 else (frame % 2 == 1)
        piece = QUEEN if show_queen else PAWN
        image = self.piece_image(piece, POWER_UP_FLASH[frame % len(POWER_UP_FLASH)])
        self.screen.blit(image, image.get_rect(center=(rect.centerx, rect.centery + 4)))

    def draw_ui(self):
        title = self.title_font.render("Pawn = Queen", True, TEXT)
        self.screen.blit(title, title.get_rect(center=(WIDTH // 2, TOP // 2)))

        hover = self.reset_rect.collidepoint(pygame.mouse.get_pos())
        pygame.draw.rect(self.screen, BUTTON_HOVER if hover else BUTTON, self.reset_rect, border_radius=10)
        pygame.draw.rect(self.screen, FRAME_EDGE, self.reset_rect, 2, border_radius=10)
        label = self.text_font.render("Reset", True, TEXT)
        self.screen.blit(label, label.get_rect(center=self.reset_rect.center))

    def draw_celebration(self):
        elapsed = pygame.time.get_ticks() - self.win_time
        if elapsed < 4000 and random.random() < 0.7:
            for _ in range(3):
                self.confetti.append(Confetti(random.uniform(0, WIDTH), -10))
        for c in self.confetti:
            c.update()
            c.draw(self.screen)
        self.confetti = [c for c in self.confetti if c.y < HEIGHT + 20]

        if elapsed > 400:
            scale = 1 + 0.06 * math.sin(elapsed / 180)
            banner = self.banner_font.render("Puzzle solved!", True, (255, 215, 60))
            banner = pygame.transform.rotozoom(banner, 0, scale)
            shadow = pygame.transform.rotozoom(self.banner_font.render("Puzzle solved!", True, OUTLINE), 0, scale)
            centre = (WIDTH // 2, BOARD_TOP + BOARD_PX // 2)
            self.screen.blit(shadow, shadow.get_rect(center=(centre[0] + 3, centre[1] + 3)))
            self.screen.blit(banner, banner.get_rect(center=centre))

    def draw(self):
        self.screen.fill(BACKGROUND)
        self.draw_board()
        self.draw_pieces()
        self.draw_ui()
        if self.won:
            self.draw_celebration()
        pygame.display.flip()

    # ------------------------------------------------------------ main loop
    def run(self):
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    self.handle_click(event.pos)
                if event.type == pygame.KEYDOWN and event.key == pygame.K_r:
                    self.reset()
            if self.shake:
                self.shake -= 1
            self.draw()
            self.clock.tick(60)


if __name__ == "__main__":
    Game().run()
