import pygame
import pygame_gui
import random
import math
import json
import os
from collections import deque

# Initialize Pygame
pygame.init()
pygame.mixer.init()

# Constants
SCREEN_WIDTH = 1920
SCREEN_HEIGHT = 1080
FPS = 60

# Colors
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
GRAY = (128, 128, 128)
DARK_GRAY = (50, 50, 50)
GREEN = (0, 255, 0)
DARK_GREEN = (0, 128, 0)
RED = (255, 0, 0)
DARK_RED = (139, 0, 0)
BLUE = (0, 0, 255)
GOLD = (255, 215, 0)
BROWN = (139, 69, 19)
CYAN = (0, 255, 255)
YELLOW = (255, 255, 0)

# Save files
SAVE_FILE = "savegame.json"
SETTINGS_FILE = "settings.json"

# Initial state
INITIAL_STATE = {
    "level": 1,
    "gold": 0,
    "stash": 0,
    "class": None,
    "player_hp": 40,
    "max_hp": 40,
    "mana": 30,
    "max_mana": 30,
    "xp": 0,
    "xp_next": 100,
    "char_lvl": 1,
    "attack_power": 10,
    "def": 2,
    "map_w": 12,  # Start at 12x12
    "map_h": 12,
    "in_town": True,
    "torch_radius": 5.5,
    "has_portal": False,
    "inv": {"h_pot": 2, "m_pot": 2}
}

# Default settings
DEFAULT_SETTINGS = {
    "master_volume": 0.7,
    "music_volume": 0.5,
    "sfx_volume": 0.8,
    "fullscreen": False,
    "vsync": True,
    "show_fps": False
}

# Settings (will be loaded from file)
settings = DEFAULT_SETTINGS.copy()

def load_settings():
    """Load settings from file"""
    global settings
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r") as f:
                loaded = json.load(f)
                settings.update(loaded)
        except:
            pass

def save_settings():
    """Save settings to file"""
    try:
        with open(SETTINGS_FILE, "w") as f:
            json.dump(settings, f, indent=2)
        return True
    except:
        return False

# --- PATHFINDING & DUNGEON GENERATION ---
def get_path(start, target, grid):
    """BFS Pathfinding"""
    if not grid or not start or not target:
        return None
    
    start_t, target_t = tuple(start), tuple(target)
    queue = deque([start_t])
    visited = {start_t}
    parent = {}
    
    while queue:
        curr = queue.popleft()
        if curr == target_t:
            path = []
            while curr in parent:
                path.append(curr)
                curr = parent[curr]
            return path
        
        for move in [[0,1], [0,-1], [1,0], [-1,0]]:
            nxt = (curr[0]+move[0], curr[1]+move[1])
            if 0 <= nxt[0] < len(grid) and 0 <= nxt[1] < len(grid[0]):
                if grid[nxt[0]][nxt[1]] == '.' and nxt not in visited:
                    visited.add(nxt)
                    parent[nxt] = curr
                    queue.append(nxt)
    return None

def ensure_path(start, target, grid):
    """Drills through walls if no valid path exists"""
    if not grid or not start or not target:
        return
    
    if get_path(start, target, grid): 
        return
    
    curr = list(start)
    while curr != target:
        if curr[0] < target[0]: curr[0] += 1
        elif curr[0] > target[0]: curr[0] -= 1
        elif curr[1] < target[1]: curr[1] += 1
        elif curr[1] > target[1]: curr[1] -= 1
        
        if 0 <= curr[0] < len(grid) and 0 <= curr[1] < len(grid[0]):
            grid[curr[0]][curr[1]] = '.'

def has_line_of_sight(start, end, grid):
    """Bresenham's line algorithm for line of sight"""
    if not grid:
        return False
    
    x0, y0 = start
    x1, y1 = end
    dx, dy = abs(x1 - x0), abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx - dy
    curr_x, curr_y = x0, y0
    
    while (curr_x, curr_y) != (x1, y1):
        if grid[curr_x][curr_y] == '#' and (curr_x, curr_y) != start: 
            return False
        e2 = 2 * err
        if e2 > -dy: 
            err -= dy
            curr_x += sx
        if e2 < dx: 
            err += dx
            curr_y += sy
    return True

def build_level_caves(w, h):
    """Generate cave-style dungeon (floors 1-20) - tight tunnels"""
    grid = [['#' for _ in range(w)] for _ in range(h)]
    
    # Fewer walkers, shorter walks = tighter caves
    for _ in range(4): 
        curr = [random.randint(2, h-3), random.randint(2, w-3)]
        for _ in range(int(w * h * 0.25)):  # Less open space
            grid[curr[0]][curr[1]] = '.'
            move = random.choice([[0,1], [0,-1], [1,0], [-1,0]])
            curr[0] = max(1, min(h-2, curr[0] + move[0]))
            curr[1] = max(1, min(w-2, curr[1] + move[1]))
    return grid

def build_level_catacombs(w, h):
    """Generate catacomb-style dungeon (floors 21-40) - room + corridor"""
    grid = [['#' for _ in range(w)] for _ in range(h)]
    
    # Create rooms
    num_rooms = random.randint(4, 6)
    rooms = []
    
    for _ in range(num_rooms):
        room_w = random.randint(3, 5)
        room_h = random.randint(3, 5)
        x = random.randint(1, w - room_w - 1)
        y = random.randint(1, h - room_h - 1)
        
        # Carve out room
        for r in range(y, y + room_h):
            for c in range(x, x + room_w):
                grid[r][c] = '.'
        
        rooms.append((y + room_h//2, x + room_w//2))
    
    # Connect rooms with corridors
    for i in range(len(rooms) - 1):
        r1, c1 = rooms[i]
        r2, c2 = rooms[i + 1]
        
        # Horizontal then vertical corridor
        for c in range(min(c1, c2), max(c1, c2) + 1):
            if 0 < c < w - 1:
                grid[r1][c] = '.'
        for r in range(min(r1, r2), max(r1, r2) + 1):
            if 0 < r < h - 1:
                grid[r][c2] = '.'
    
    return grid

def build_level_dungeon(w, h):
    """Generate classic dungeon (floors 41-60) - structured rooms"""
    grid = [['#' for _ in range(w)] for _ in range(h)]
    
    # Grid of rooms with guaranteed spacing
    room_size = 3
    spacing = 3
    
    for room_y in range(1, h - room_size - 1, room_size + spacing):
        for room_x in range(1, w - room_size - 1, room_size + spacing):
            # Always create room (don't skip randomly)
            for r in range(room_y, min(room_y + room_size, h - 1)):
                for c in range(room_x, min(room_x + room_size, w - 1)):
                    if 0 < r < h - 1 and 0 < c < w - 1:
                        grid[r][c] = '.'
            
            # Add horizontal corridor if there's room
            if room_x + room_size + spacing < w - 1:
                for c in range(room_x + room_size, min(room_x + room_size + spacing, w - 1)):
                    if 0 < c < w - 1 and 0 < room_y + 1 < h - 1:
                        grid[room_y + 1][c] = '.'
            
            # Add vertical corridor if there's room
            if room_y + room_size + spacing < h - 1:
                for r in range(room_y + room_size, min(room_y + room_size + spacing, h - 1)):
                    if 0 < r < h - 1 and 0 < room_x + 1 < w - 1:
                        grid[r][room_x + 1] = '.'
    
    return grid

def build_level_ruins(w, h):
    """Generate ruins (floors 61+) - open with pillars"""
    grid = [['.' for _ in range(w)] for _ in range(h)]  # Fixed: '.' not '. '
    
    # Outer walls
    for c in range(w):
        grid[0][c] = '#'
        grid[h-1][c] = '#'
    for r in range(h):
        grid[r][0] = '#'
        grid[r][w-1] = '#'
    
    # Random pillars and walls
    for _ in range(int(w * h * 0.15)):
        r = random.randint(1, h-2)
        c = random.randint(1, w-2)
        grid[r][c] = '#'
    
    return grid

def build_level_boss(w, h):
    """Generate boss arena - large open room"""
    grid = [['#' for _ in range(w)] for _ in range(h)]
    
    # Large central arena
    center_w = w - 4
    center_h = h - 4
    
    for r in range(2, h - 2):
        for c in range(2, w - 2):
            grid[r][c] = '.'
    
    # Optional pillars in corners
    if w > 10 and h > 10:
        grid[3][3] = '#'
        grid[3][w-4] = '#'
        grid[h-4][3] = '#'
        grid[h-4][w-4] = '#'
    
    return grid

def build_level(w, h, level):
    """Generate dungeon based on floor level"""
    # Boss floors always get boss arena
    if level % 10 == 0:
        return build_level_boss(w, h)
    
    # Different styles by depth
    if level <= 20:
        return build_level_caves(w, h)
    elif level <= 40:
        return build_level_catacombs(w, h)
    elif level <= 60:
        return build_level_dungeon(w, h)
    else:
        return build_level_ruins(w, h)

def init_new_floor(state):
    """Initialize a new dungeon floor"""
    w, h = state["map_w"], state["map_h"]
    level = state["level"]
    grid = build_level(w, h, level)  # Pass level for style selection
    
    def get_pos(occupied):
        for _ in range(1000):
            r, c = random.randint(1, h-2), random.randint(1, w-2)
            if grid[r][c] == '.' and [r, c] not in occupied: 
                return [r, c]
        return [h//2, w//2]
    
    # Place player
    p = get_pos([])
    
    # Boss every 10 levels
    is_boss = (state["level"] % 10 == 0)
    
    # Calculate number of enemies (1 per 10 levels, but only 1 on boss floors)
    if is_boss:
        num_enemies = 1
        e_hp = (25 + (state["level"] * 12)) * 3  # Triple HP for boss
    else:
        # After each boss, add one more enemy
        # Levels 1-9: 1 enemy, 11-19: 2 enemies, 21-29: 3 enemies
        num_enemies = (state["level"] // 10) + 1
        e_hp = 25 + (state["level"] * 12)
    
    # Place enemies
    enemies = []
    occupied = [p]
    for i in range(num_enemies):
        e_pos = get_pos(occupied)
        enemies.append({
            "pos": e_pos,
            "hp": e_hp,
            "is_boss": is_boss and i == 0  # Only first enemy is boss
        })
        occupied.append(e_pos)
    
    # Place other entities
    c = get_pos(occupied)
    occupied.append(c)
    s = get_pos(occupied)
    occupied.append(s)
    f = get_pos(occupied)
    
    # Ensure paths exist
    for enemy in enemies:
        ensure_path(p, enemy["pos"], grid)
    for target in [c, s, f]: 
        ensure_path(p, target, grid)
    
    return {
        "grid": grid, 
        "p": p, 
        "enemies": enemies,  # List of enemies
        "c": c, 
        "s": s, 
        "f": f, 
        "is_boss": is_boss,
        "visible_tiles": set()
    }

def update_visibility(dungeon, state):
    """Update visible tiles based on torch radius and line of sight"""
    if not dungeon.get("grid") or not dungeon.get("p"):
        return
    
    visible = set()
    p = dungeon["p"]
    grid = dungeon["grid"]
    radius = state["torch_radius"]
    
    for r in range(len(grid)):
        for c in range(len(grid[0])):
            distance = math.sqrt((r - p[0])**2 + (c - p[1])**2)
            if distance <= radius and has_line_of_sight(p, [r, c], grid):
                visible.add((r, c))
    
    dungeon["visible_tiles"] = visible

class Game:
    def __init__(self):
        # Load settings first
        load_settings()
        
        # ALWAYS start in windowed mode (override saved fullscreen setting)
        settings["fullscreen"] = False
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        
        pygame.display.set_caption("AIDA: Master Expedition")
        self.clock = pygame.time.Clock()
        self.running = True
        self.font_small = pygame.font.Font(None, 24)
        self.font_medium = pygame.font.Font(None, 32)
        self.font_large = pygame.font.Font(None, 48)
        
        # Use monospace font for ASCII art
        try:
            self.font_mono = pygame.font.SysFont('couriernew', 16, bold=True)
        except:
            self.font_mono = pygame.font.SysFont('courier', 16, bold=True)
        
        # Game state
        self.state = INITIAL_STATE.copy()
        self.session_dungeon = {}
        self.portal_storage = {"grid": None}
        self.save_state = {}
        
        # Combat log
        self.combat_log = []
        self.max_log_lines = 50  # Store more lines
        self.log_scroll_offset = 0  # Scroll position
        self.max_visible_log_lines = 8  # How many lines to show
        
        # UI state
        self.show_settings = False
        self.show_shop = False
        self.show_inn = False
        
        # pygame_gui manager
        self.ui_manager = pygame_gui.UIManager((SCREEN_WIDTH, SCREEN_HEIGHT))
        
        # Load game if exists
        self.load_game()
        
        # Initialize audio system
        self.audio = AudioSystem()
    
    def log(self, message):
        """Add message to combat log"""
        self.combat_log.append(message)
        if len(self.combat_log) > self.max_log_lines:
            self.combat_log.pop(0)
        # Don't print to console - only show in game
    
    def load_game(self):
        if os.path.exists(SAVE_FILE):
            try:
                with open(SAVE_FILE, "r") as f:
                    loaded = json.load(f)
                    self.state.update(loaded)
            except:
                pass
    
    def save_game(self):
        try:
            with open(SAVE_FILE, "w") as f:
                json.dump(self.state, f, indent=2)
            return True
        except:
            return False
    
    def run(self):
        while self.running:
            time_delta = self.clock.tick(FPS) / 1000.0
            self.handle_events(time_delta)
            self.update()
            self.draw()
            self.ui_manager.update(time_delta)
            self.ui_manager.draw_ui(self.screen)
            pygame.display.flip()
        
        pygame.quit()
    
    def handle_events(self, time_delta):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            
            # Mouse wheel scrolling for combat log in dungeon
            if event.type == pygame.MOUSEWHEEL and not self.state["in_town"]:
                self.log_scroll_offset = max(0, min(
                    len(self.combat_log) - self.max_visible_log_lines,
                    self.log_scroll_offset - event.y
                ))
            
            # Let UI manager process events first
            self.ui_manager.process_events(event)
            
            # Game input handling
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    # Close any open menu
                    if self.show_shop:
                        self.show_shop = False
                    elif self.show_inn:
                        self.show_inn = False
                    else:
                        self.show_settings = not self.show_settings
                elif event.key == pygame.K_F11:
                    self.toggle_fullscreen()
                elif not self.state["in_town"] and not self.show_settings and not self.show_shop and not self.show_inn:
                    self.handle_dungeon_input(event)
            
            if event.type == pygame.MOUSEBUTTONDOWN:
                self.handle_mouse_click(event.pos)
    
    def handle_dungeon_input(self, event):
        # Movement
        if event.key in (pygame.K_w, pygame.K_UP):
            self.move_player(0, -1)
        elif event.key in (pygame.K_s, pygame.K_DOWN):
            self.move_player(0, 1)
        elif event.key in (pygame.K_a, pygame.K_LEFT):
            self.move_player(-1, 0)
        elif event.key in (pygame.K_d, pygame.K_RIGHT):
            self.move_player(1, 0)
        elif event.key == pygame.K_h:
            self.use_health_potion()
        elif event.key == pygame.K_m:
            self.use_mana_potion()
        elif event.key == pygame.K_SPACE:
            self.use_skill()
    
    def handle_mouse_click(self, pos):
        # Settings gear button (top right, not overlapping recall)
        settings_rect = pygame.Rect(SCREEN_WIDTH - 60, 10, 50, 50)
        if settings_rect.collidepoint(pos):
            self.show_settings = True
            return
        
        # Dungeon clicks
        if not self.state["in_town"]:
            recall_rect = pygame.Rect(SCREEN_WIDTH - 200, 30, 150, 50)
            if recall_rect.collidepoint(pos):
                self.recall_to_town()
                return
            
            # Combat log scroll arrows
            if hasattr(self, 'log_up_arrow_rect') and self.log_up_arrow_rect.collidepoint(pos):
                self.log_scroll_offset = max(0, self.log_scroll_offset - 1)
                return
            
            if hasattr(self, 'log_down_arrow_rect') and self.log_down_arrow_rect.collidepoint(pos):
                max_scroll = max(0, len(self.combat_log) - self.max_visible_log_lines)
                self.log_scroll_offset = min(max_scroll, self.log_scroll_offset + 1)
                return
            
            if hasattr(self, 'h_pot_rect') and self.h_pot_rect.collidepoint(pos):
                self.use_health_potion()
                return
            
            if hasattr(self, 'm_pot_rect') and self.m_pot_rect.collidepoint(pos):
                self.use_mana_potion()
                return
            
            if hasattr(self, 'skill_rect') and self.skill_rect.collidepoint(pos):
                self.use_skill()
                return
        else:
            # Town clicks
            self.handle_town_click(pos)
    
    def handle_town_click(self, pos):
        """Handle clicks in town"""
        # Class selection or town options
        if self.state["class"] is None:
            self.check_class_selection(pos)
        else:
            self.check_town_options(pos)
    
    def check_class_selection(self, pos):
        """Check if clicked on class selection"""
        classes = ["Warrior", "Mage", "Rogue", "Cleric"]
        y_offset = 200
        
        for i, class_name in enumerate(classes):
            x = SCREEN_WIDTH // 2 - 200
            y = y_offset + i * 130
            button_rect = pygame.Rect(x, y, 400, 110)
            
            if button_rect.collidepoint(pos):
                self.select_class(class_name)
                break
    
    def check_town_options(self, pos):
        """Check if clicked on town options"""
        options = [("inn", 300), ("shop", 450), ("dungeon", 600)]
        
        for action, y in options:
            x = SCREEN_WIDTH // 2 - 200
            button_rect = pygame.Rect(x, y, 400, 80)
            
            if button_rect.collidepoint(pos):
                if action == "inn":
                    self.show_inn = True
                elif action == "shop":
                    self.show_shop = True
                elif action == "dungeon":
                    self.enter_dungeon()
                break
    
    def select_class(self, class_name):
        """Apply class bonuses"""
        if self.state["class"] is not None:
            return
        
        self.state["class"] = class_name
        
        if class_name == "Warrior":
            self.state["max_hp"] += 20
            self.state["attack_power"] = 12
            self.state["def"] = 3
        elif class_name == "Mage":
            self.state["max_mana"] += 30
            self.state["torch_radius"] = 7.5
            self.state["attack_power"] = 8
        elif class_name == "Rogue":
            self.state["attack_power"] = 15
            self.state["def"] = 5
            self.state["torch_radius"] = 6.5
        elif class_name == "Cleric":
            self.state["max_hp"] += 15
            self.state["max_mana"] += 15
            self.state["def"] = 5
            self.state["attack_power"] = 9
        
        self.state["player_hp"] = self.state["max_hp"]
        self.state["mana"] = self.state["max_mana"]
        self.log(f"✨ Selected {class_name} class!")
    
    def enter_dungeon(self):
        """Enter the dungeon"""
        if self.state["class"] is None:
            self.log("❌ Please select a class first!")
            return
        
        self.state["in_town"] = False
        
        if self.portal_storage["grid"] is None:
            self.session_dungeon = init_new_floor(self.state)
        else:
            self.session_dungeon = self.portal_storage.copy()
        
        update_visibility(self.session_dungeon, self.state)
        self.log("⚔️ Entering dungeon...")
    
    def move_player(self, dx, dy):
        """Move player in dungeon"""
        if not self.session_dungeon.get("grid") or not self.session_dungeon.get("p"):
            self.log("⚠️ Error: Invalid dungeon state. Regenerating...")
            self.session_dungeon = init_new_floor(self.state)
            update_visibility(self.session_dungeon, self.state)
            return
        
        p = self.session_dungeon["p"]
        enemies = self.session_dungeon.get("enemies", [])
        grid = self.session_dungeon["grid"]
        
        new_pos = [p[0] + dy, p[1] + dx]
        
        if not (0 <= new_pos[0] < len(grid) and 0 <= new_pos[1] < len(grid[0])):
            return
        
        if grid[new_pos[0]][new_pos[1]] == '#':
            return
        
        # Check if attacking any enemy
        attacked_enemy = None
        for enemy in enemies:
            if new_pos == enemy["pos"] and enemy["hp"] > 0:
                attacked_enemy = enemy
                break
        
        if attacked_enemy:
            damage = random.randint(8, 12) + self.state["attack_power"] - 10
            attacked_enemy["hp"] -= damage
            self.log(f"⚔ You hit for {damage} damage! (Enemy: {max(0, attacked_enemy['hp'])} HP)")
            
            if attacked_enemy["hp"] <= 0:
                xp_gain = 40 + (self.state["level"] * 10)
                if attacked_enemy.get("is_boss"):
                    xp_gain *= 3
                self.state["xp"] += xp_gain
                self.log(f"Enemy slain! +{xp_gain} XP")
                attacked_enemy["pos"] = [-1, -1]  # Move off map
                self.check_level_up()
        else:
            # Normal movement
            p[0], p[1] = new_pos
        
        update_visibility(self.session_dungeon, self.state)
        self.enemy_turn()
        self.check_tile_interactions()
    
    def enemy_turn(self):
        """Enemy AI - all enemies take turns"""
        if not self.session_dungeon.get("grid"):
            return
        
        enemies = self.session_dungeon.get("enemies", [])
        p = self.session_dungeon["p"]
        grid = self.session_dungeon["grid"]
        
        # Each living enemy takes a turn
        for enemy in enemies:
            if enemy["hp"] <= 0:
                continue
            
            e = enemy["pos"]
            
            # Check if player is visible to this enemy
            if tuple(e) in self.session_dungeon["visible_tiles"]:
                temp_e = list(e)
                if e[0] != p[0]: 
                    temp_e[0] += 1 if e[0] < p[0] else -1
                elif e[1] != p[1]: 
                    temp_e[1] += 1 if e[1] < p[1] else -1
                
                # Check if attacking player
                if temp_e == p:
                    enemy_dmg = max(1, (8 + self.state["level"] + 
                                       (5 if enemy.get("is_boss") else 0)) - self.state["def"])
                    self.state["player_hp"] -= enemy_dmg
                    boss_text = " (BOSS)" if enemy.get("is_boss") else ""
                    self.log(f"💥 Enemy{boss_text} attacks for {enemy_dmg} damage! (You: {self.state['player_hp']}/{self.state['max_hp']} HP)")
                    
                    if self.state["player_hp"] <= 0:
                        self.game_over()
                        return  # Stop processing if player died
                else:
                    # Check if another enemy is already there
                    occupied = False
                    for other_enemy in enemies:
                        if other_enemy != enemy and other_enemy["hp"] > 0 and other_enemy["pos"] == temp_e:
                            occupied = True
                            break
                    
                    # Normal movement if path is clear
                    dest_valid = (0 <= temp_e[0] < len(grid) and 
                                 0 <= temp_e[1] < len(grid[0]) and
                                 grid[temp_e[0]][temp_e[1]] == '.' and
                                 not occupied)
                    
                    if dest_valid:
                        e[0], e[1] = temp_e
            else:
                # Random wander
                mv = random.choice([[0,1], [0,-1], [1,0], [-1,0]])
                temp_e = [e[0] + mv[0], e[1] + mv[1]]
                
                # Check if another enemy is there
                occupied = False
                for other_enemy in enemies:
                    if other_enemy != enemy and other_enemy["hp"] > 0 and other_enemy["pos"] == temp_e:
                        occupied = True
                        break
                
                if (0 <= temp_e[0] < len(grid) and 
                    0 <= temp_e[1] < len(grid[0]) and
                    grid[temp_e[0]][temp_e[1]] == '.' and
                    temp_e != p and
                    not occupied):
                    e[0], e[1] = temp_e
    
    def check_tile_interactions(self):
        """Check for chest, stairs, fountain"""
        # Safety check
        if not self.session_dungeon.get("grid") or not self.session_dungeon.get("p"):
            return
        
        p = self.session_dungeon["p"]
        enemies = self.session_dungeon.get("enemies", [])
        
        if p == self.session_dungeon["c"]:
            gold_gain = random.randint(40, 80) + (self.state["level"] * 5)
            self.state["gold"] += gold_gain
            self.log(f"💰 Chest! +{gold_gain} gold")
            self.session_dungeon["c"] = [-1, -1]
        
        # Stairs only usable when ALL enemies are dead
        all_enemies_dead = all(enemy["hp"] <= 0 for enemy in enemies)
        if p == self.session_dungeon["s"] and all_enemies_dead:
            self.descend_stairs()
        
        if p == self.session_dungeon["f"]:
            self.state["player_hp"] = self.state["max_hp"]
            self.state["mana"] = self.state["max_mana"]
            self.log("💧 Holy Fountain! HP and MP restored!")
            self.session_dungeon["f"] = [-1, -1]
    
    def descend_stairs(self):
        """Go to next floor"""
        self.state["level"] += 1
        
        # Expand map WIDTH every 3 levels (12 -> 14 -> 16 ... -> 28 columns)
        if self.state["level"] % 3 == 0 and self.state["map_w"] < 28:
            self.state["map_w"] += 2  # Add 2 columns
            # Height stays same or grows slower
            if self.state["map_h"] < 20:
                self.state["map_h"] += 1  # Slight height increase
            self.log(f"📏 Map expanded to {self.state['map_w']}x{self.state['map_h']}!")
        
        self.session_dungeon = init_new_floor(self.state)
        update_visibility(self.session_dungeon, self.state)
        
        if self.state["level"] % 10 == 0:
            self.log(f"⚠️ BOSS LEVEL {self.state['level']}!")
        else:
            self.log(f"Descended to depth {self.state['level']}m")
    
    def check_level_up(self):
        """Check level up"""
        while self.state["xp"] >= self.state["xp_next"]:
            self.state["char_lvl"] += 1
            self.state["xp"] -= self.state["xp_next"]
            self.state["xp_next"] = int(self.state["xp_next"] * 1.5)
            self.state["max_hp"] += 10
            self.state["max_mana"] += 5
            self.state["attack_power"] += 2
            self.state["def"] += 1
            self.state["player_hp"] = self.state["max_hp"]
            self.state["mana"] = self.state["max_mana"]
            self.log(f"⭐ LEVEL UP! Now level {self.state['char_lvl']}!")
    
    def game_over(self):
        """Handle death"""
        # Check if player has rested at inn (has a save point)
        if self.save_state.get("player_hp", 0) > 0:
            # Restore from last inn save
            self.log("💀 DEFEAT! Waking up at the inn from your last rest...")
            self.state = self.save_state.copy()
            self.state["in_town"] = True
            self.state["gold"] = 0  # Lose dungeon gold on death
            self.portal_storage = {"grid": None}
            self.session_dungeon = {}
        else:
            # Permadeath - no inn save
            self.log("💀 GAME OVER - No inn save! Creating new character...")
            self.state = INITIAL_STATE.copy()
            self.save_state = {}
            self.portal_storage = {"grid": None}
            self.session_dungeon = {}
            self.combat_log = []
            # Delete save file
            if os.path.exists(SAVE_FILE):
                os.remove(SAVE_FILE)
    
    def use_health_potion(self):
        """Use health potion"""
        if self.state["inv"]["h_pot"] > 0:
            self.state["inv"]["h_pot"] -= 1
            heal = min(30, self.state["max_hp"] - self.state["player_hp"])
            self.state["player_hp"] += heal
            self.log(f"🧪 Used Health Potion! Restored {heal} HP")
    
    def use_mana_potion(self):
        """Use mana potion"""
        if self.state["inv"]["m_pot"] > 0:
            self.state["inv"]["m_pot"] -= 1
            restore = min(20, self.state["max_mana"] - self.state["mana"])
            self.state["mana"] += restore
            self.log(f"🧪 Used Mana Potion! Restored {restore} MP")
    
    def use_skill(self):
        """Use class skill"""
        if self.state["mana"] < 10:
            self.log("❌ Not enough mana! Need 10 MP")
            return
        
        class_name = self.state.get("class")
        if not class_name:
            self.log("❌ No class selected!")
            return
        
        self.state["mana"] -= 10
        
        # Find closest visible living enemy
        enemies = self.session_dungeon.get("enemies", [])
        p = self.session_dungeon["p"]
        visible = self.session_dungeon["visible_tiles"]
        
        closest_enemy = None
        min_dist = float('inf')
        
        for enemy in enemies:
            if enemy["hp"] > 0 and tuple(enemy["pos"]) in visible:
                dist = abs(enemy["pos"][0] - p[0]) + abs(enemy["pos"][1] - p[1])
                if dist < min_dist:
                    min_dist = dist
                    closest_enemy = enemy
        
        if class_name == "Warrior" and closest_enemy:
            damage = self.state["attack_power"] * 2
            closest_enemy["hp"] -= damage
            self.log(f"⚔️ Power Strike! Dealt {damage} damage!")
        elif class_name == "Mage" and closest_enemy:
            damage = self.state["attack_power"] + 25
            closest_enemy["hp"] -= damage
            self.log(f"🔥 Fireball! Dealt {damage} damage!")
        elif class_name == "Rogue" and closest_enemy:
            damage = self.state["attack_power"] + random.randint(15, 30)
            closest_enemy["hp"] -= damage
            self.log(f"🗡️ Backstab! Dealt {damage} damage!")
        elif class_name == "Cleric":
            heal = min(30, self.state["max_hp"] - self.state["player_hp"])
            self.state["player_hp"] += heal
            self.log(f"✨ Heal! Restored {heal} HP!")
        
        # Check if enemy died
        if closest_enemy and closest_enemy["hp"] <= 0:
            xp_gain = 40 + (self.state["level"] * 10)
            if closest_enemy.get("is_boss"):
                xp_gain *= 3
            self.state["xp"] += xp_gain
            self.log(f"Enemy slain! +{xp_gain} XP")
            closest_enemy["pos"] = [-1, -1]
            self.check_level_up()
    
    def recall_to_town(self):
        """Return to town"""
        # Check if player has portal scroll
        if not self.state.get("has_portal", False):
            self.log("❌ No portal scroll! Floor resets to level 1!")
            self.state["level"] = 1
            self.state["map_w"] = 12  # Reset to 12x12
            self.state["map_h"] = 12
            self.portal_storage = {"grid": None}
        else:
            # Use portal scroll
            self.state["has_portal"] = False
            self.log("📜 Used Portal Scroll! Dungeon progress saved!")
            # Save dungeon state
            self.portal_storage = self.session_dungeon.copy()
        
        # Auto-bank gold to stash
        banked = self.state["gold"]
        self.state["stash"] += banked
        self.state["gold"] = 0
        self.log(f"💰 Auto-banked {banked}g to stash! (Total stash: {self.state['stash']}g)")
        
        # Return to town
        self.state["in_town"] = True
        self.session_dungeon = {}
        
        # Save the game state
        self.save_game()
    
    def toggle_fullscreen(self):
        """Toggle fullscreen"""
        settings["fullscreen"] = not settings["fullscreen"]
        
        if settings["fullscreen"]:
            # Get desktop size for fullscreen
            info = pygame.display.Info()
            self.screen = pygame.display.set_mode((info.current_w, info.current_h), pygame.FULLSCREEN)
            self.log("🖥️ Switched to fullscreen mode")
        else:
            self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
            self.log("🪟 Switched to windowed mode")
        
        # Recreate UI manager with new screen size
        current_size = self.screen.get_size()
        self.ui_manager = pygame_gui.UIManager(current_size)
        
        save_settings()
    
    def update(self):
        pass
    
    def draw(self):
        self.screen.fill(DARK_GRAY)
        
        if self.show_settings:
            if self.state["in_town"]:
                self.draw_town()
            else:
                self.draw_dungeon()
            self.draw_settings()
        elif self.show_shop:
            self.draw_town()
            self.draw_shop()
        elif self.show_inn:
            self.draw_town()
            self.draw_inn()
        elif self.state["in_town"]:
            self.draw_town()
        else:
            self.draw_dungeon()
        
        self.draw_settings_button()
        
        if settings["show_fps"]:
            fps_text = self.font_small.render(f"FPS: {int(self.clock.get_fps())}", True, WHITE)
            self.screen.blit(fps_text, (10, 10))
    
    def draw_settings_button(self):
        """Draw settings gear icon (top right, not overlapping recall)"""
        button_rect = pygame.Rect(SCREEN_WIDTH - 60, 10, 50, 50)
        mouse_pos = pygame.mouse.get_pos()
        
        if button_rect.collidepoint(mouse_pos):
            pygame.draw.rect(self.screen, (100, 100, 100), button_rect)
        else:
            pygame.draw.rect(self.screen, GRAY, button_rect)
        
        pygame.draw.rect(self.screen, WHITE, button_rect, 2)
        
        # Gear symbol (⚙ works if font supports it)
        try:
            text = self.font_large.render("⚙", True, WHITE)
            self.screen.blit(text, (button_rect.x + 8, button_rect.y + 3))
        except:
            # Fallback if gear symbol doesn't render
            text = self.font_medium.render("SET", True, WHITE)
            self.screen.blit(text, (button_rect.x + 5, button_rect.y + 15))
    
    def draw_town(self):
        """Draw town screen"""
        title = self.font_large.render("⚔ ODIN'S REST ⚔", True, GOLD)
        self.screen.blit(title, (SCREEN_WIDTH//2 - title.get_width()//2, 50))
        
        y_offset = 200
        if self.state["class"] is None:
            self.draw_class_selection(y_offset)
        else:
            self.draw_town_options(y_offset)
    
    def draw_class_selection(self, y_offset):
        """Draw class selection"""
        classes = [
            ("Warrior", "High HP, Heavy Armor\n+20 HP | +2 ATK | +1 DEF\nPower Strike (2x dmg, 1 tile)", RED),
            ("Mage", "High Mana, Long Range\n+30 MP | -2 ATK | +2.5 Vision\nFireball (high dmg, 5 tiles)", BLUE),
            ("Rogue", "Balanced, High Damage\n+5 ATK | +3 DEF | +1.5 Vision\nBackstab (variable dmg, 2 tiles)", GREEN),
            ("Cleric", "Healer, Support\n+15 HP | +15 MP | +3 DEF\nHeal (restore HP, 0 tiles)", CYAN)
        ]
        
        mouse_pos = pygame.mouse.get_pos()
        
        for i, (name, desc, color) in enumerate(classes):
            x = SCREEN_WIDTH // 2 - 200
            y = y_offset + i * 130
            button_rect = pygame.Rect(x, y, 400, 110)
            
            if button_rect.collidepoint(mouse_pos):
                pygame.draw.rect(self.screen, color, button_rect)
                pygame.draw.rect(self.screen, WHITE, button_rect, 5)
            else:
                pygame.draw.rect(self.screen, color, button_rect)
                pygame.draw.rect(self.screen, WHITE, button_rect, 3)
            
            name_text = self.font_medium.render(name, True, WHITE)
            self.screen.blit(name_text, (x + 10, y + 10))
            
            desc_lines = desc.split('\n')
            for j, line in enumerate(desc_lines):
                line_text = self.font_small.render(line, True, WHITE)
                self.screen.blit(line_text, (x + 10, y + 45 + j * 22))
    
    def draw_town_options(self, y_offset):
        """Draw town options"""
        options = [
            ("🏠 INN", "Rest & Save (10g)", BROWN, 300),
            ("🏪 SHOP", "Buy Items & Upgrades", BLUE, 450),
            ("⚔ ENTER DUNGEON", "Descend into the depths", DARK_RED, 600)
        ]
        
        mouse_pos = pygame.mouse.get_pos()
        
        for name, desc, color, y in options:
            x = SCREEN_WIDTH // 2 - 200
            button_rect = pygame.Rect(x, y, 400, 80)
            
            if button_rect.collidepoint(mouse_pos):
                hover_color = tuple(min(c + 50, 255) for c in color)
                pygame.draw.rect(self.screen, hover_color, button_rect)
                pygame.draw.rect(self.screen, WHITE, button_rect, 5)
            else:
                pygame.draw.rect(self.screen, color, button_rect)
                pygame.draw.rect(self.screen, WHITE, button_rect, 3)
            
            name_text = self.font_medium.render(name, True, WHITE)
            desc_text = self.font_small.render(desc, True, WHITE)
            self.screen.blit(name_text, (x + 10, y + 10))
            self.screen.blit(desc_text, (x + 10, y + 45))
    
    def draw_dungeon(self):
        """Draw dungeon view"""
        if not self.session_dungeon.get("grid"):
            text = self.font_large.render("Initializing dungeon...", True, WHITE)
            self.screen.blit(text, (SCREEN_WIDTH//2 - text.get_width()//2, SCREEN_HEIGHT//2))
            return
        
        self.draw_dungeon_map()
        self.draw_dungeon_hud()
    
    def draw_dungeon_map(self):
        """Draw ASCII dungeon with layering"""
        grid = self.session_dungeon["grid"]
        p = self.session_dungeon["p"]
        enemies = self.session_dungeon.get("enemies", [])
        c = self.session_dungeon["c"]
        s = self.session_dungeon["s"]
        f = self.session_dungeon["f"]
        visible = self.session_dungeon["visible_tiles"]
        is_boss = self.session_dungeon.get("is_boss", False)
        
        # Convert positions to tuples for comparison
        p_tuple = tuple(p) if p else None
        c_tuple = tuple(c) if c else None
        s_tuple = tuple(s) if s else None
        f_tuple = tuple(f) if f else None
        
        # Convert all enemy positions to tuples
        enemy_positions = {}
        for enemy in enemies:
            if enemy["hp"] > 0:
                enemy_positions[tuple(enemy["pos"])] = enemy
        
        start_x = 50
        start_y = 100
        char_width = 12
        line_height = 20
        
        # Column headers (support up to 28 columns = A-AB)
        header_chars = []
        for i in range(min(len(grid[0]), 28)):
            if i < 26:
                header_chars.append(chr(65 + i))
            else:
                # After Z, use AA, AB, etc
                header_chars.append("A" + chr(65 + (i - 26)))
        header = "     " + " ".join(header_chars)
        header_surf = self.font_mono.render(header, True, WHITE)
        self.screen.blit(header_surf, (start_x, start_y))
        
        # Draw each row
        for r in range(len(grid)):
            # Row number
            row_num = f"{r+1:2d}   "
            row_num_surf = self.font_mono.render(row_num, True, WHITE)
            self.screen.blit(row_num_surf, (start_x, start_y + (r + 1) * line_height))
            
            # Draw each cell
            for col in range(len(grid[0])):
                pos = (r, col)
                x = start_x + 40 + col * char_width
                y = start_y + (r + 1) * line_height
                
                # LAYER 1: Terrain (gray walls, green floor)
                if pos not in visible:
                    terrain_char = "█"
                    terrain_color = (30, 30, 30)  # Dark fog
                elif grid[r][col] == '#':
                    terrain_char = "█"
                    terrain_color = (128, 128, 128)  # Gray walls
                else:
                    terrain_char = "."
                    terrain_color = (0, 160, 0)  # Green floor
                
                terrain_surf = self.font_mono.render(terrain_char, True, terrain_color)
                self.screen.blit(terrain_surf, (x, y))
                
                # LAYER 2: Entities (on top of terrain)
                if pos in visible:
                    entity_char = None
                    entity_color = None
                    
                    # Check each entity (compare tuples)
                    if pos == p_tuple:
                        entity_char = "@"
                        entity_color = (0, 255, 255)  # Cyan (light blue) player
                    elif pos in enemy_positions:
                        enemy = enemy_positions[pos]
                        entity_char = "B" if enemy["is_boss"] else "E"
                        entity_color = (200, 0, 0) if enemy["is_boss"] else (255, 100, 100)
                    elif pos == c_tuple:
                        entity_char = "$"
                        entity_color = (255, 215, 0)  # Gold chest
                    elif pos == s_tuple and all(e["hp"] <= 0 for e in enemies):
                        entity_char = ">"
                        entity_color = (0, 255, 255)  # Cyan stairs (easy to see)
                    elif pos == f_tuple:
                        entity_char = "F"
                        entity_color = (100, 149, 237)  # Blue fountain
                    
                    if entity_char:
                        entity_surf = self.font_mono.render(entity_char, True, entity_color)
                        self.screen.blit(entity_surf, (x, y))
    
    def draw_dungeon_hud(self):
        """Draw dungeon HUD"""
        # Header with dungeon style
        level = self.state["level"]
        if level % 10 == 0:
            style = "BOSS ARENA"
        elif level <= 20:
            style = "Caves"
        elif level <= 40:
            style = "Catacombs"
        elif level <= 60:
            style = "Dungeon"
        else:
            style = "Ruins"
        
        depth_text = self.font_large.render(f"DEPTH: {level}m ({style})", True, WHITE)
        self.screen.blit(depth_text, (50, 30))
        
        # Recall button
        recall_rect = pygame.Rect(SCREEN_WIDTH - 200, 30, 150, 50)
        mouse_pos = pygame.mouse.get_pos()
        color = (0, 0, 200) if recall_rect.collidepoint(mouse_pos) else BLUE
        pygame.draw.rect(self.screen, color, recall_rect)
        pygame.draw.rect(self.screen, WHITE, recall_rect, 2)
        recall_text = self.font_medium.render("RECALL", True, WHITE)
        self.screen.blit(recall_text, (recall_rect.centerx - recall_text.get_width()//2, recall_rect.centery - 15))
        
        # Sidebar
        sidebar_x = SCREEN_WIDTH - 350
        sidebar_y = 150
        
        stats = [
            f"Class: {self.state.get('class', 'None')}",
            f"Level: {self.state['char_lvl']}",
            f"ATK: {self.state['attack_power']}",
            f"DEF: {self.state['def']}"
        ]
        
        for i, stat in enumerate(stats):
            text = self.font_small.render(stat, True, WHITE)
            self.screen.blit(text, (sidebar_x, sidebar_y + i * 30))
        
        # Inventory
        inv_title = self.font_medium.render("INVENTORY", True, GOLD)
        self.screen.blit(inv_title, (sidebar_x, sidebar_y + 150))
        
        # Health Potion
        h_pot_rect = pygame.Rect(sidebar_x, sidebar_y + 190, 120, 40)
        color = (200, 0, 0) if h_pot_rect.collidepoint(mouse_pos) and self.state["inv"]["h_pot"] > 0 else RED
        pygame.draw.rect(self.screen, color, h_pot_rect)
        pygame.draw.rect(self.screen, WHITE, h_pot_rect, 2)
        h_text = self.font_small.render(f"H-Pot x{self.state['inv']['h_pot']}", True, WHITE)
        self.screen.blit(h_text, (h_pot_rect.x + 10, h_pot_rect.y + 10))
        self.h_pot_rect = h_pot_rect
        
        # Mana Potion
        m_pot_rect = pygame.Rect(sidebar_x, sidebar_y + 240, 120, 40)
        color = (0, 0, 200) if m_pot_rect.collidepoint(mouse_pos) and self.state["inv"]["m_pot"] > 0 else BLUE
        pygame.draw.rect(self.screen, color, m_pot_rect)
        pygame.draw.rect(self.screen, WHITE, m_pot_rect, 2)
        m_text = self.font_small.render(f"M-Pot x{self.state['inv']['m_pot']}", True, WHITE)
        self.screen.blit(m_text, (m_pot_rect.x + 10, m_pot_rect.y + 10))
        self.m_pot_rect = m_pot_rect
        
        # Portal scroll status
        if self.state.get("has_portal", False):
            portal_text = self.font_small.render("Portal: YES", True, GREEN)
        else:
            portal_text = self.font_small.render("Portal: NO", True, RED)
        self.screen.blit(portal_text, (sidebar_x, sidebar_y + 290))
        
        # Skill button
        skill_rect = pygame.Rect(sidebar_x, sidebar_y + 320, 200, 50)
        color = (128, 0, 128) if skill_rect.collidepoint(mouse_pos) else (75, 0, 130)
        pygame.draw.rect(self.screen, color, skill_rect)
        pygame.draw.rect(self.screen, WHITE, skill_rect, 2)
        skill_text = self.font_medium.render("SKILL (Space)", True, WHITE)
        self.screen.blit(skill_text, (skill_rect.x + 10, skill_rect.y + 15))
        self.skill_rect = skill_rect
        
        # Skill description
        skill_descs = {
            "Warrior": "Power Strike (2x ATK, 1 tile)",
            "Mage": "Fireball (ATK+25, 5 tiles)",
            "Rogue": "Backstab (ATK+15-30, 2 tiles)",
            "Cleric": "Heal (Restore 30 HP)"
        }
        desc = skill_descs.get(self.state.get("class"), "No class")
        desc_text = self.font_small.render(desc, True, YELLOW)
        self.screen.blit(desc_text, (sidebar_x, sidebar_y + 380))
        
        # Progress bars
        bar_y = SCREEN_HEIGHT - 220
        bar_width = 300
        bar_height = 25
        
        # HP
        hp_pct = self.state["player_hp"] / self.state["max_hp"]
        hp_rect = pygame.Rect(50, bar_y, bar_width, bar_height)
        pygame.draw.rect(self.screen, DARK_GRAY, hp_rect)
        pygame.draw.rect(self.screen, RED, pygame.Rect(50, bar_y, int(bar_width * hp_pct), bar_height))
        pygame.draw.rect(self.screen, WHITE, hp_rect, 2)
        hp_text = self.font_small.render(f"HP: {self.state['player_hp']}/{self.state['max_hp']}", True, WHITE)
        self.screen.blit(hp_text, (hp_rect.centerx - hp_text.get_width()//2, hp_rect.centery - 10))
        
        # MP
        mp_pct = self.state["mana"] / self.state["max_mana"]
        mp_rect = pygame.Rect(400, bar_y, bar_width, bar_height)
        pygame.draw.rect(self.screen, DARK_GRAY, mp_rect)
        pygame.draw.rect(self.screen, BLUE, pygame.Rect(400, bar_y, int(bar_width * mp_pct), bar_height))
        pygame.draw.rect(self.screen, WHITE, mp_rect, 2)
        mp_text = self.font_small.render(f"MP: {self.state['mana']}/{self.state['max_mana']}", True, WHITE)
        self.screen.blit(mp_text, (mp_rect.centerx - mp_text.get_width()//2, mp_rect.centery - 10))
        
        # XP
        xp_pct = self.state["xp"] / self.state["xp_next"]
        xp_rect = pygame.Rect(750, bar_y, bar_width, bar_height)
        pygame.draw.rect(self.screen, DARK_GRAY, xp_rect)
        pygame.draw.rect(self.screen, GOLD, pygame.Rect(750, bar_y, int(bar_width * xp_pct), bar_height))
        pygame.draw.rect(self.screen, WHITE, xp_rect, 2)
        xp_text = self.font_small.render(f"XP: {self.state['xp']}/{self.state['xp_next']}", True, WHITE)
        self.screen.blit(xp_text, (xp_rect.centerx - xp_text.get_width()//2, xp_rect.centery - 10))
        
        # Gold
        gold_text = self.font_medium.render(f"GOLD: {self.state['gold']}", True, GOLD)
        self.screen.blit(gold_text, (SCREEN_WIDTH - 300, bar_y))
        
        # Combat log - positioned between progress bars and bottom
        log_y = SCREEN_HEIGHT - 250  # Lower position, above bottom edge
        log_bg = pygame.Rect(40, log_y, 770, 180)  # Slightly smaller height
        pygame.draw.rect(self.screen, (20, 20, 20), log_bg)
        pygame.draw.rect(self.screen, GRAY, log_bg, 2)
        
        log_title = self.font_medium.render("COMBAT LOG", True, GOLD)
        self.screen.blit(log_title, (50, log_y + 5))
        
        # Calculate visible log range
        start_idx = max(0, len(self.combat_log) - self.max_visible_log_lines - self.log_scroll_offset)
        end_idx = start_idx + self.max_visible_log_lines
        visible_messages = self.combat_log[start_idx:end_idx]
        
        for i, message in enumerate(visible_messages):
            log_text = self.font_small.render(message, True, WHITE)
            self.screen.blit(log_text, (50, log_y + 40 + i * 20))
        
        # Scroll bar on the right
        scrollbar_x = log_bg.right - 25
        scrollbar_y = log_bg.y + 35
        scrollbar_height = log_bg.height - 70
        
        # Scroll bar background
        scrollbar_bg = pygame.Rect(scrollbar_x, scrollbar_y, 20, scrollbar_height)
        pygame.draw.rect(self.screen, DARK_GRAY, scrollbar_bg)
        pygame.draw.rect(self.screen, WHITE, scrollbar_bg, 1)
        
        # Up arrow button
        up_arrow_rect = pygame.Rect(scrollbar_x, log_bg.y + 35, 20, 20)
        pygame.draw.rect(self.screen, GRAY, up_arrow_rect)
        pygame.draw.rect(self.screen, WHITE, up_arrow_rect, 1)
        up_arrow = self.font_small.render("^", True, WHITE)
        self.screen.blit(up_arrow, (up_arrow_rect.centerx - 5, up_arrow_rect.centery - 10))
        
        # Down arrow button
        down_arrow_rect = pygame.Rect(scrollbar_x, log_bg.bottom - 25, 20, 20)
        pygame.draw.rect(self.screen, GRAY, down_arrow_rect)
        pygame.draw.rect(self.screen, WHITE, down_arrow_rect, 1)
        down_arrow = self.font_small.render("v", True, WHITE)
        self.screen.blit(down_arrow, (down_arrow_rect.centerx - 5, down_arrow_rect.centery - 10))
        
        # Store rects for click detection
        self.log_up_arrow_rect = up_arrow_rect
        self.log_down_arrow_rect = down_arrow_rect
        
        # Scroll indicator
        if len(self.combat_log) > self.max_visible_log_lines:
            scroll_text = self.font_small.render(f"({len(self.combat_log) - end_idx} more)", True, YELLOW)
            self.screen.blit(scroll_text, (600, log_y + 5))
    
    def draw_settings(self):
        """Draw settings overlay"""
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        overlay.set_alpha(200)
        overlay.fill(BLACK)
        self.screen.blit(overlay, (0, 0))
        
        panel_rect = pygame.Rect(SCREEN_WIDTH//2 - 300, 150, 600, 600)
        pygame.draw.rect(self.screen, DARK_GRAY, panel_rect)
        pygame.draw.rect(self.screen, WHITE, panel_rect, 3)
        
        title = self.font_large.render("⚙ SETTINGS", True, GOLD)
        self.screen.blit(title, (SCREEN_WIDTH//2 - title.get_width()//2, 170))
        
        mouse_pos = pygame.mouse.get_pos()
        
        # Close button
        close_rect = pygame.Rect(SCREEN_WIDTH//2 + 200, 160, 80, 40)
        if close_rect.collidepoint(mouse_pos):
            pygame.draw.rect(self.screen, (200, 0, 0), close_rect)
        else:
            pygame.draw.rect(self.screen, RED, close_rect)
        pygame.draw.rect(self.screen, WHITE, close_rect, 2)
        close_text = self.font_medium.render("X", True, WHITE)
        self.screen.blit(close_text, (close_rect.centerx - 10, close_rect.centery - 15))
        
        if pygame.mouse.get_pressed()[0] and close_rect.collidepoint(mouse_pos):
            self.show_settings = False
            pygame.time.wait(200)
            return
        
        # Instructions
        instructions = [
            "F11 - Toggle Fullscreen",
            "ESC - Close Menu",
            "H - Health Potion",
            "M - Mana Potion",
            "SPACE - Use Skill",
            "WASD/Arrows - Move",
            "Mouse Wheel - Scroll Log"
        ]
        
        for i, inst in enumerate(instructions):
            text = self.font_medium.render(inst, True, WHITE)
            self.screen.blit(text, (SCREEN_WIDTH//2 - text.get_width()//2, 250 + i * 40))
        
        # Save Game button
        save_rect = pygame.Rect(SCREEN_WIDTH//2 - 150, 550, 300, 60)
        if save_rect.collidepoint(mouse_pos):
            pygame.draw.rect(self.screen, DARK_GREEN, save_rect)
            pygame.draw.rect(self.screen, WHITE, save_rect, 5)
            
            if pygame.mouse.get_pressed()[0]:
                self.save_game()
                self.log("💾 Game saved!")
                pygame.time.wait(200)
        else:
            pygame.draw.rect(self.screen, GREEN, save_rect)
            pygame.draw.rect(self.screen, WHITE, save_rect, 3)
        
        save_text = self.font_large.render("SAVE GAME", True, WHITE)
        self.screen.blit(save_text, (save_rect.centerx - save_text.get_width()//2, save_rect.centery - 20))
        
        # Exit Game button
        exit_rect = pygame.Rect(SCREEN_WIDTH//2 - 150, 630, 300, 60)
        if exit_rect.collidepoint(mouse_pos):
            pygame.draw.rect(self.screen, (200, 0, 0), exit_rect)
            pygame.draw.rect(self.screen, WHITE, exit_rect, 5)
            
            if pygame.mouse.get_pressed()[0]:
                self.save_game()
                self.running = False
        else:
            pygame.draw.rect(self.screen, DARK_RED, exit_rect)
            pygame.draw.rect(self.screen, WHITE, exit_rect, 3)
        
        exit_text = self.font_large.render("EXIT GAME", True, WHITE)
        self.screen.blit(exit_text, (exit_rect.centerx - exit_text.get_width()//2, exit_rect.centery - 20))
    
    def draw_shop(self):
        """Draw shop overlay"""
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        overlay.set_alpha(200)
        overlay.fill(BLACK)
        self.screen.blit(overlay, (0, 0))
        
        mouse_pos = pygame.mouse.get_pos()  # Define mouse_pos at the start
        
        # Shop panel
        panel_rect = pygame.Rect(SCREEN_WIDTH//2 - 350, 80, 700, 650)
        pygame.draw.rect(self.screen, DARK_GRAY, panel_rect)
        pygame.draw.rect(self.screen, WHITE, panel_rect, 3)
        
        # Title
        title = self.font_large.render("🏪 SHOP", True, GOLD)
        self.screen.blit(title, (SCREEN_WIDTH//2 - title.get_width()//2, 100))
        
        # Stash is your shop gold (permanent, safe money)
        stash_text = self.font_medium.render(f"Stash (Shop Gold): {self.state['stash']}g", True, YELLOW)
        self.screen.blit(stash_text, (SCREEN_WIDTH//2 - 300, 150))
        
        # Close button
        close_rect = pygame.Rect(SCREEN_WIDTH//2 + 250, 110, 80, 40)
        if close_rect.collidepoint(mouse_pos):
            pygame.draw.rect(self.screen, (200, 0, 0), close_rect)
        else:
            pygame.draw.rect(self.screen, RED, close_rect)
        pygame.draw.rect(self.screen, WHITE, close_rect, 2)
        close_text = self.font_medium.render("X", True, WHITE)
        self.screen.blit(close_text, (close_rect.centerx - 10, close_rect.centery - 15))
        
        # Check close button click
        if pygame.mouse.get_pressed()[0] and close_rect.collidepoint(mouse_pos):
            self.show_shop = False
            pygame.time.wait(300)  # Longer delay to prevent double-click
            return
        
        # Shop items
        items = [
            ("Health Potion", 15, "h_pot", "Restores 30 HP"),
            ("Mana Potion", 15, "m_pot", "Restores 20 MP"),
            ("Portal Scroll", 30, "portal", "Return to town"),
            ("Sharp Sword", 50, "sword", "+3 ATK"),
            ("Heavy Armor", 50, "armor", "+15 HP"),
            ("Lantern", 75, "lantern", "+1.5 Vision")
        ]
        
        center_x = SCREEN_WIDTH // 2
        start_y = 200  # Back to original position
        
        for i, (name, cost, item_id, desc) in enumerate(items):
            button_rect = pygame.Rect(center_x - 300, start_y + i * 70, 600, 60)
            
            # Hover effect
            if button_rect.collidepoint(mouse_pos):
                pygame.draw.rect(self.screen, BLUE, button_rect)
                pygame.draw.rect(self.screen, WHITE, button_rect, 4)
                
                # Handle click
                if pygame.mouse.get_pressed()[0]:
                    self.purchase_item(item_id, cost, name)
                    pygame.time.wait(200)
            else:
                pygame.draw.rect(self.screen, DARK_GRAY, button_rect)
                pygame.draw.rect(self.screen, GRAY, button_rect, 2)
            
            # Item text
            name_text = self.font_medium.render(f"{name} - {cost}g", True, WHITE)
            desc_text = self.font_small.render(desc, True, CYAN)
            self.screen.blit(name_text, (button_rect.x + 10, button_rect.y + 10))
            self.screen.blit(desc_text, (button_rect.x + 10, button_rect.y + 35))
    
    def purchase_item(self, item_id, cost, name):
        """Purchase an item using stash gold"""
        state = self.state
        
        if state["stash"] < cost:
            self.log(f"❌ Not enough gold! Need {cost}g (Stash: {state['stash']}g)")
            return
        
        if item_id in ["h_pot", "m_pot"]:
            state["inv"][item_id] += 1
            state["stash"] -= cost
            self.log(f"✅ Purchased {name}!")
        elif item_id == "portal":
            state["has_portal"] = True
            state["stash"] -= cost
            self.log(f"✅ Purchased {name}!")
        elif item_id == "sword":
            state["attack_power"] += 3
            state["stash"] -= cost
            self.log(f"✅ Purchased {name}! ATK +3")
        elif item_id == "armor":
            state["max_hp"] += 15
            state["player_hp"] += 15
            state["stash"] -= cost
            self.log(f"✅ Purchased {name}! HP +15")
        elif item_id == "lantern":
            state["torch_radius"] += 1.5
            state["stash"] -= cost
            self.log(f"✅ Purchased {name}! Vision +1.5")
    
    def draw_inn(self):
        """Draw inn overlay"""
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        overlay.set_alpha(200)
        overlay.fill(BLACK)
        self.screen.blit(overlay, (0, 0))
        
        # Inn panel
        panel_rect = pygame.Rect(SCREEN_WIDTH//2 - 300, 80, 600, 500)
        pygame.draw.rect(self.screen, DARK_GRAY, panel_rect)
        pygame.draw.rect(self.screen, WHITE, panel_rect, 3)
        
        # Title
        title = self.font_large.render("🏠 THE INN", True, GOLD)
        self.screen.blit(title, (SCREEN_WIDTH//2 - title.get_width()//2, 100))
        
        # Close button
        close_rect = pygame.Rect(SCREEN_WIDTH//2 + 200, 110, 80, 40)
        mouse_pos = pygame.mouse.get_pos()
        if close_rect.collidepoint(mouse_pos):
            pygame.draw.rect(self.screen, (200, 0, 0), close_rect)
        else:
            pygame.draw.rect(self.screen, RED, close_rect)
        pygame.draw.rect(self.screen, WHITE, close_rect, 2)
        close_text = self.font_medium.render("X", True, WHITE)
        self.screen.blit(close_text, (close_rect.centerx - 10, close_rect.centery - 15))
        
        # Check close button click
        if pygame.mouse.get_pressed()[0] and close_rect.collidepoint(mouse_pos):
            self.show_inn = False
            pygame.time.wait(300)  # Longer delay
            return
        
        # Innkeeper quote
        quote = self.font_medium.render('"Rest ye weary traveler"', True, CYAN)
        self.screen.blit(quote, (SCREEN_WIDTH//2 - quote.get_width()//2, 180))
        
        innkeeper = self.font_medium.render('- Innkeeper Olaf', True, WHITE)
        self.screen.blit(innkeeper, (SCREEN_WIDTH//2 - innkeeper.get_width()//2, 220))
        
        # Show last rest message if exists
        if hasattr(self, 'last_rest_message'):
            rest_msg = self.font_small.render(self.last_rest_message, True, GREEN)
            self.screen.blit(rest_msg, (SCREEN_WIDTH//2 - rest_msg.get_width()//2, 260))
        
        # Rest button
        rest_rect = pygame.Rect(SCREEN_WIDTH//2 - 150, 320, 300, 80)
        if rest_rect.collidepoint(mouse_pos):
            pygame.draw.rect(self.screen, BROWN, rest_rect)
            pygame.draw.rect(self.screen, WHITE, rest_rect, 5)
            
            # Handle click
            if pygame.mouse.get_pressed()[0]:
                self.rest_at_inn()
                pygame.time.wait(200)
        else:
            pygame.draw.rect(self.screen, BROWN, rest_rect)
            pygame.draw.rect(self.screen, WHITE, rest_rect, 3)
        
        rest_text = self.font_large.render("Rest & Save", True, WHITE)
        cost_text = self.font_medium.render("10g", True, GOLD)
        self.screen.blit(rest_text, (rest_rect.centerx - rest_text.get_width()//2, rest_rect.y + 15))
        self.screen.blit(cost_text, (rest_rect.centerx - cost_text.get_width()//2, rest_rect.y + 50))
        
        # Stats display (show STASH not gold since gold is 0 in town)
        stats_y = 450
        stats = [
            f"Stash: {self.state['stash']}g",
            f"HP: {self.state['player_hp']}/{self.state['max_hp']}",
            f"MP: {self.state['mana']}/{self.state['max_mana']}"
        ]
        
        for i, stat in enumerate(stats):
            stat_text = self.font_small.render(stat, True, WHITE)
            self.screen.blit(stat_text, (SCREEN_WIDTH//2 - 100 + i * 100, stats_y))
    
    def rest_at_inn(self):
        """Rest at inn - costs 10g from STASH"""
        if self.state["stash"] >= 10:
            self.state["stash"] -= 10  # Pay from stash, not gold
            self.state["player_hp"] = self.state["max_hp"]
            self.state["mana"] = self.state["max_mana"]
            self.save_game()
            self.save_state = self.state.copy()
            self.last_rest_message = "✅ Rested! HP/MP restored & game saved!"
            self.log("💤 Rested at inn! HP and MP restored, game saved!")
        else:
            self.last_rest_message = "❌ Not enough gold! (Need 10g in stash)"
            self.log("❌ Not enough gold to rest! Need 10g in stash")

class AudioSystem:
    def __init__(self):
        self.sounds = {}
        self.music_playing = None
    
    def play_sound(self, sound_name, position=None, player_pos=None):
        """Play sound with optional positional audio"""
        pass
    
    def play_music(self, track_name):
        """Play background music"""
        pass

if __name__ == "__main__":
    game = Game()
    game.run()