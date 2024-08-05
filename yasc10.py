#################################################################################
#                                                                               #
# YASC is an offline implementation of Splix.io with bots, written in Python3   #
# Copyright (C) 2024 by paws9678 @ Discord                                      #
#                                                                               #
# This program is free software: you can redistribute it and/or modify          #
# it under the terms of the GNU [Affero] General Public License as published by #
# the Free Software Foundation, either version 3 of the License, or             #
# (at your option) any later version.                                           #
#                                                                               #
# This program is distributed in the hope that it will be useful,               #
# but WITHOUT ANY WARRANTY; without even the implied warranty of                #
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the                 #
# GNU [Affero] General Public License for more details.                         #
#                                                                               #
# You should have received a copy of the GNU [Affero] General Public License    #
# along with this program.  If not, see <https://www.gnu.org/licenses/>.        #
#                                                                               #
# YASC may only be distributed together with its LICENSE and ReadMe files.      #
#                                                                               #
#################################################################################

# Please feel free to experiment with different values. Have fun! :)
#
# These constants are probably the most interesting for you:
# MIN_AREA, NUM_BOTS, MIN_SPAWN_DISTANCE, BOT_VS_BOT_AGGRESSION, BOT_VS_PLAYER_AGGRESSION, PLAYER_PROXIMITY_FACTOR and PROXIMITY_THRESHOLD
# maybe also TILE_SIZE (but this isn't tested as thoroughly)


import pygame
import random
import colorsys
from collections import deque
import string
import time
import pickle
import os

# Initialize Pygame
pygame.init()
pygame.font.init()
territories = {}

# PLAYFIELD_SIZE = 100
TILE_SIZE = 11
ORIGINAL_RADAR_SIZE = 262
RADAR_SIZE = ORIGINAL_RADAR_SIZE
RADAR_SHRINK = 19
SHRUNKEN_RADAR_SIZE = RADAR_SIZE - RADAR_SHRINK
frame_counter = 0

def generate_unique_colors(n):
    colors = set()
    golden_ratio_conjugate = 0.618033988749895
    hue = random.random()
    
    for _ in range(n):
        hue += golden_ratio_conjugate
        hue %= 1
        rgb = colorsys.hsv_to_rgb(hue, 0.8, 0.8)
        color = tuple(int(c * 255) for c in rgb)
        while color in colors:
            hue += golden_ratio_conjugate
            hue %= 1
            rgb = colorsys.hsv_to_rgb(hue, 0.8, 0.8)
            color = tuple(int(c * 255) for c in rgb)
        colors.add(color)
    
    return list(colors)


NUM_BOTS = 40
BOT_COLORS = generate_unique_colors(NUM_BOTS)
# print(f"Generated {len(BOT_COLORS)} unique colors")

NUM_ENTITIES = NUM_BOTS +1
MIN_SPAWN_DISTANCE = 9
# MIN_AREA = (NUM_ENTITIES * (MIN_SPAWN_DISTANCE ** 2) * 4) // 3  # Adding some extra space
MIN_AREA = 120 ** 2
NEW_GRID_SIZE = int(MIN_AREA ** 0.5) + 1
# print(f"New grid size: {NEW_GRID_SIZE}")
GRID_SIZE = NEW_GRID_SIZE
VIEWPORT_TILES = min(80, GRID_SIZE)  # Adjust viewport size if needed
VIEWPORT_SIZE = VIEWPORT_TILES * TILE_SIZE
SCORE_TABLE_HEIGHT = 530
WINDOW_WIDTH = VIEWPORT_SIZE + RADAR_SIZE + 20  # Add some padding
WINDOW_HEIGHT = max(VIEWPORT_SIZE, RADAR_SIZE + SCORE_TABLE_HEIGHT) + 30  # Ensure enough height for both radar and score table

# Bot aggression parameters
BOT_VS_BOT_AGGRESSION = 0.0  # 0.5  # Default value, range 0-1
BOT_VS_PLAYER_AGGRESSION = 1.0 # 0.7  # Default value, range 0-1
PLAYER_PROXIMITY_FACTOR = 3.0   # 1.2  # Multiplier for aggression when near player
PROXIMITY_THRESHOLD = 15  # 30  # Distance to player to trigger increased aggression

# Colors
BACKGROUND_COLOR = (40, 40, 40)
GRID_COLOR = (0, 0, 0)
PLAYER_COLOR = (255, 255, 255)
BOT_COLOR = (200, 200, 200)
PLAYER_TERRITORY_COLOR = (0, 60, 0)
TRAIL_COLOR = (0, 120, 0)
RADAR_BACKGROUND_COLOR = (0, 40, 0)
RADAR_TERRITORY_COLOR = (0, 90, 0)
GREEN_100 = (0, 100, 0)

game_started = False
game_paused = False
last_score_update_time = 0
cached_score_surface = None
last_scores = {}

screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
pygame.display.set_caption("YASC - Yet Another Splix Clone v1.0")


def save_game(player, bots, score_manager, territories, filename="savegame.pkl"):
    game_state = {
        'player': {
            'position': (player.x, player.y),
            'trail': player.trail,
            'territory': player.territory,
            'color': player.color,
            'name': player.name,
            'id': player.id
        },
        'bots': [{
            'position': (bot.x, bot.y),
            'trail': bot.trail,
            'territory': bot.territory,
            'color': bot.color,
            'name': bot.name,
            'id': bot.id
        } for bot in bots],
        'scores': score_manager.scores,
        'territories': {entity.name: territory for entity, territory in territories.items()}
    }
    
    with open(filename, 'wb') as f:
        pickle.dump(game_state, f)
    print(f"Game saved to {filename}")


def load_game(filename="savegame.pkl"):
    if not os.path.exists(filename):
        print(f"Save file {filename} not found.")
        return None

    with open(filename, 'rb') as f:
        game_state = pickle.load(f)
    
    # Recreate player
    player_data = game_state['player']
    player = Player(player_data['position'][0], player_data['position'][1], player_data['color'])
    player.trail = player_data['trail']
    player.territory = player_data['territory']
    player.name = player_data['name']
    player.id = player_data['id']

    # Recreate bots
    bots = []
    for bot_data in game_state['bots']:
        bot = Bot(bot_data['position'][0], bot_data['position'][1])
        bot.trail = bot_data['trail']
        bot.territory = bot_data['territory']
        bot.color = bot_data['color']
        bot.name = bot_data['name']
        bot.id = bot_data['id']
        bots.append(bot)

    # Recreate score manager
    score_manager = ScoreManager()
    score_manager.scores = game_state['scores']

    # Recreate territories
    territories = {next((e for e in [player] + bots if e.name == name), name): territory 
                   for name, territory in game_state['territories'].items()}

    print(f"Game loaded from {filename}")
    return player, bots, score_manager, territories


def is_on_border(x, y):
    return x < 0 or x >= GRID_SIZE or y < 0 or y >= GRID_SIZE


def distance(pos1, pos2):
    return ((pos1[0] - pos2[0]) ** 2 + (pos1[1] - pos2[1]) ** 2) ** 0.5


def find_valid_spawn_position(existing_entities):
    border_distance = 3
    attempts = 0
    max_attempts = 200  # 1000  # Prevent infinite loop

    while attempts < max_attempts:
        x = random.randint(border_distance, GRID_SIZE - 1 - border_distance)
        y = random.randint(border_distance, GRID_SIZE - 1 - border_distance)
        
        # Check if the position is not in any player's territory
        if all((x, y) not in entity.territory for entity in existing_entities if not isinstance(entity, Bot)):
            # Check distance from existing entities
            if all(distance((x, y), (e.x, e.y)) >= MIN_SPAWN_DISTANCE for e in existing_entities):
                # If it's not in a bot's territory, return immediately
                if not any((x, y) in entity.territory for entity in existing_entities if isinstance(entity, Bot)):
                    return x, y
                # If it's in a bot's territory, keep it as a potential position
                potential_position = (x, y)

        attempts += 1

    # If we couldn't find a position outside all territories, return the last potential position (in a bot's territory)
    if 'potential_position' in locals():
        return potential_position

    # If we still couldn't find a position, fall back to the original method
    return find_valid_spawn_position_original(existing_entities)


def find_valid_spawn_position_original(existing_entities):
    border_distance = 3
    while True:
        x = random.randint(border_distance, GRID_SIZE - 1 - border_distance)
        y = random.randint(border_distance, GRID_SIZE - 1 - border_distance)
        if all(distance((x, y), (e.x, e.y)) >= MIN_SPAWN_DISTANCE for e in existing_entities):
            return x, y



def darker_shade(color, factor=0.5):
    return tuple(int(c * factor) for c in color)


class Player:
    next_id = 1
    def __init__(self, x, y, color):
        self.x = x
        self.y = y
        self.color = color
        self.trail_color = color
        self.territory_color = darker_shade(color)
        self.territory = set((x + dx, y + dy) for dx in range(-2, 3) for dy in range(-2, 3))
        self.trail = []
        self.moving = False
        self.direction = None
        self.last_direction = None
        self.change_direction_counter = 0
        self.name = "Player"
        self.id = Player.next_id
        Player.next_id += 1

    @staticmethod
    def is_in_lethal_zone(x, y):
        return x == 0 or x == GRID_SIZE - 1 or y == 0 or y == GRID_SIZE - 1

    def is_valid_move(self, x, y):
        return (1 <= x < GRID_SIZE - 1 and 1 <= y < GRID_SIZE - 1 and 
                (x, y) not in self.trail)

    def is_safe_move(self, x, y):
        return self.is_valid_move(x, y)


    def set_direction(self, new_direction):
        if not self.moving:
            self.direction = new_direction
            self.moving = True
        elif (self.x, self.y) in self.territory:
            self.direction = new_direction
        else:
            if not self.is_opposite_direction(new_direction):
                self.direction = new_direction
        
        if self.direction:
            self.last_direction = self.direction


    def is_opposite_direction(self, new_direction):
        if not self.last_direction:
            return False
        return (self.last_direction[0] == -new_direction[0] and 
                self.last_direction[1] == -new_direction[1])


    def move(self):
        if self.direction and self.moving:
            new_x = self.x + self.direction[0]
            new_y = self.y + self.direction[1]
            if not is_on_border(new_x, new_y):
                self.x, self.y = new_x, new_y
                if (self.x, self.y) not in self.territory:
                    self.trail.append((self.x, self.y))
            else:
                self.moving = False


    def claim_territory(self, positions):
        self.territory.update(positions)
        for entity in all_entities:
            if entity != self:
                entity.territory -= set(positions)



    def expand_territory(self):
        if not self.trail:
            return

        if len(self.trail) <= GRID_SIZE*2:
            if not self.entities_inside_trail():
                new_territory = set(self.trail)
                self.fill_interior()
                new_territory.update(self.territory - set(self.trail))
                self.claim_territory(new_territory)

        self.trail.clear()


    def entities_inside_trail(self):
        # This method should check if any entities (player or bots) are inside the area
        # enclosed by the trail and the existing territory
        # For now, we'll assume there are no entities to check
        return False


    def fill_interior(self):
        if not self.trail:
            return

        # Find the bounding box of the trail
        min_x = min(x for x, y in self.trail)
        max_x = max(x for x, y in self.trail)
        min_y = min(y for x, y in self.trail)
        max_y = max(y for x, y in self.trail)

        # Create a set of boundary points (trail + existing territory)
        boundary = set(self.trail) | self.territory

        # Find a point inside the trail to start the flood fill
        start_point = None
        for x in range(min_x, max_x + 1):
            for y in range(min_y, max_y + 1):
                if (x, y) not in boundary and self.is_point_inside((x, y)):
                    start_point = (x, y)
                    break
            if start_point:
                break

        if not start_point:
            return  # No interior point found

        # Perform flood fill
        queue = deque([start_point])
        filled = set()

        while queue:
            x, y = queue.popleft()
            if (x, y) in filled or (x, y) in boundary:
                continue

            filled.add((x, y))

            # Check neighboring points
            for dx, dy in [(0, 1), (1, 0), (0, -1), (-1, 0)]:
                nx, ny = x + dx, y + dy
                if min_x <= nx <= max_x and min_y <= ny <= max_y:
                    queue.append((nx, ny))

        # Add the filled points to the territory
        self.territory.update(filled)

    def is_point_inside(self, point):
        x, y = point
        if (x, y) in self.territory or (x, y) in self.trail:
            return False  # Point is already in territory or on the trail

        # Cast a ray from the point to the right
        intersections = 0
        for i in range(len(self.trail)):
            p1 = self.trail[i]
            p2 = self.trail[(i + 1) % len(self.trail)]
            if (p1[1] > y) != (p2[1] > y):
                if x < (p2[0] - p1[0]) * (y - p1[1]) / (p2[1] - p1[1]) + p1[0]:
                    intersections += 1

        # If the number of intersections is odd, the point is inside
        return intersections % 2 == 1

    """
    def fill_interior(self):
        if not self.trail:
            return

        # Find the bounding box of the trail
        min_x = min(x for x, y in self.trail)
        max_x = max(x for x, y in self.trail)
        min_y = min(y for x, y in self.trail)
        max_y = max(y for x, y in self.trail)

        # Check all points within the bounding box
        for x in range(min_x, max_x + 1):
            for y in range(min_y, max_y + 1):
                if self.is_point_inside((x, y)):
                    self.territory.add((x, y))

    def is_point_inside(self, point):
        x, y = point
        if (x, y) in self.territory or (x, y) in self.trail:
            return False  # Point is already in territory or on the trail

        # Cast a ray from the point to the right
        intersections = 0
        for i in range(len(self.trail)):
            p1 = self.trail[i]
            p2 = self.trail[(i + 1) % len(self.trail)]
            if (p1[1] > y) != (p2[1] > y):
                if x < (p2[0] - p1[0]) * (y - p1[1]) / (p2[1] - p1[1]) + p1[0]:
                    intersections += 1

        # If the number of intersections is odd, the point is inside
        return intersections % 2 == 1
    """

    def check_collision_with_trail(self, trail):
        current_pos = (self.x, self.y)
        return current_pos in trail


    def check_collision_with_others_trail(self, other_entities):
        current_pos = (self.x, self.y)
        for other in other_entities:
            if other != self and current_pos in other.trail:
                return other
        return None


    def check_collision(self):
        if len(self.trail) > 1:
            head = (self.x, self.y)
            if head in self.trail[:-1]:
                return True
        return False


    def is_in_own_territory(self):
        return (self.x, self.y) in self.territory


    def check_collision_with_others(self, other_entities):
        current_pos = (self.x, self.y)
        for other in other_entities:
            if other != self and (current_pos in other.trail or current_pos in other.territory):
                return other
        return None


    def draw(self, surface, offset_x, offset_y):
        pygame.draw.rect(surface, PLAYER_COLOR, ((self.x - offset_x) * TILE_SIZE, (self.y - offset_y) * TILE_SIZE, TILE_SIZE, TILE_SIZE))


class Bot(Player):
    color_index = 0

    @classmethod
    def get_next_color(cls):
        color = BOT_COLORS[cls.color_index % len(BOT_COLORS)]
        cls.color_index += 1
        return color

    def __init__(self, x, y):
        color = self.get_next_color()
        super().__init__(x, y, color)
        self.change_direction_counter = 0
        # self.change_direction_threshold = random.randint(7, 12)
        self.change_direction_threshold = random.randint(2, 9)
        self.trail_check_counter = 0
        # self.trail_check_threshold = random.randint(4, 5)
        # self.trail_check_distance = random.randint(2, 3)
        self.trail_check_threshold = random.randint(1, 2)
        self.trail_check_distance = random.randint(5, 6)
        self.name = ""  # Will be set by ScoreManager
        # print(f"Bot created at ({x}, {y}) with color: {self.color}")
        self.max_trail_length = random.randint(6, 18)  # 15, 25
        self.aggression = random.uniform(0.2, 0.6)  # 0.5, 0.8
        self.base_aggression = random.uniform(0.1, 0.9)  # Base personality factor: default (0.4, 0.6)


    """
    @staticmethod
    def is_on_border(x, y):
        return x < 0 or x >= GRID_SIZE or y < 0 or y >= GRID_SIZE

    @staticmethod
    def is_border_tile(x, y):
        return x < 0 or x >= GRID_SIZE or y < 0 or y >= GRID_SIZE
    """


    def calculate_aggression(self, target):
        if isinstance(target, Bot):
            aggression = self.base_aggression * BOT_VS_BOT_AGGRESSION
        else:  # target is the player
            aggression = self.base_aggression * BOT_VS_PLAYER_AGGRESSION
            if self.distance_to(target) <= PROXIMITY_THRESHOLD:
                aggression *= PLAYER_PROXIMITY_FACTOR
        return min(aggression, 1.0)


    def distance_to(self, other):
        return ((self.x - other.x) ** 2 + (self.y - other.y) ** 2) ** 0.5


    def is_valid_orthogonal_move(self, from_x, from_y, to_x, to_y):
        dx = abs(to_x - from_x)
        dy = abs(to_y - from_y)
        return (dx == 1 and dy == 0) or (dx == 0 and dy == 1)


    def move(self):
        self.trail_check_counter += 1
        if self.trail_check_counter >= self.trail_check_threshold:
            nearby_trail = self.find_nearby_trail()
            if nearby_trail:
                self.target_nearby_trail(nearby_trail)
                self.trail_check_counter = 0
                self.trail_check_threshold = random.randint(4, 5)
                self.trail_check_distance = random.randint(2, 3)
            else:
                self.change_direction_counter += 1
                if self.change_direction_counter >= self.change_direction_threshold:
                    self.find_best_path()
                    self.change_direction_counter = 0
                    
                    # Adjust change_direction_threshold based on nearest entity
                    nearest_distance = self.find_nearest_entity(all_entities)
                    if nearest_distance < 10:
                        self.change_direction_threshold = random.randint(3, 6)
                    elif nearest_distance < 20:
                        self.change_direction_threshold = random.randint(5, 9)
                    else:
                        self.change_direction_threshold = random.randint(7, 12)
        else:
            self.change_direction_counter += 1
            if self.change_direction_counter >= self.change_direction_threshold:
                self.find_best_path()
                self.change_direction_counter = 0
                
                # Adjust change_direction_threshold based on nearest entity
                nearest_distance = self.find_nearest_entity(all_entities)
                if nearest_distance < 10:
                    self.change_direction_threshold = random.randint(3, 6)
                elif nearest_distance < 20:
                    self.change_direction_threshold = random.randint(5, 9)
                else:
                    self.change_direction_threshold = random.randint(7, 12)

        if self.is_about_to_trap_itself():
            self.find_best_path()

        if self.direction and self.moving:
            new_x = self.x + self.direction[0]
            new_y = self.y + self.direction[1]
            if self.is_valid_move(new_x, new_y):
                self.x, self.y = new_x, new_y
                if (self.x, self.y) not in self.territory:
                    self.trail.append((self.x, self.y))
            else:
                self.find_best_path()

    # (most recent change [24-08-04]: make bots more dynamic, they should become more cautious when enemies are nearby)



    """ previous (working) method:
    def move(self):
        # print(f"Bot at ({self.x}, {self.y}) moving in direction {self.direction}")
        
        self.trail_check_counter += 1
        if self.trail_check_counter >= self.trail_check_threshold:
            nearby_trail = self.find_nearby_trail()
            if nearby_trail:
                self.target_nearby_trail(nearby_trail)
                self.trail_check_counter = 0
                self.trail_check_threshold = random.randint(4, 5)
                self.trail_check_distance = random.randint(2, 3)
            else:
                self.change_direction_counter += 1
                if self.change_direction_counter >= self.change_direction_threshold or not self.moving:
                    self.find_best_path()
                    self.change_direction_counter = 0
                    self.change_direction_threshold = random.randint(7, 12)
        else:
            self.change_direction_counter += 1
            if self.change_direction_counter >= self.change_direction_threshold or not self.moving:
                self.find_best_path()
                self.change_direction_counter = 0
                self.change_direction_threshold = random.randint(7, 12)

        if self.is_about_to_trap_itself():
            # print(f"Bot at ({self.x}, {self.y}) detected potential self-trap, finding new path")
            self.find_best_path()

        if self.direction and self.moving:
            new_x = self.x + self.direction[0]
            new_y = self.y + self.direction[1]
            if self.is_valid_move(new_x, new_y):
                self.x, self.y = new_x, new_y
                if (self.x, self.y) not in self.territory:
                    self.trail.append((self.x, self.y))
            else:
                # print(f"Bot at ({self.x}, {self.y}) prevented from moving to ({new_x}, {new_y})")
                self.find_best_path()

        # print(f"Bot moved to ({self.x}, {self.y})")
    """

    def find_nearby_trail(self):
        check_distance = 3  # Reduced from 5
        for dx in range(-check_distance, check_distance + 1):
            for dy in range(-check_distance, check_distance + 1):
                if dx == 0 and dy == 0:
                    continue
                check_x, check_y = self.x + dx, self.y + dy
                if 0 <= check_x < GRID_SIZE and 0 <= check_y < GRID_SIZE:
                    for entity in all_entities:
                        if entity != self and (check_x, check_y) in entity.trail:
                            return (check_x, check_y)
        return None


    def find_nearby_trails(self):
        nearby_trails = []
        check_distance = 5  # Adjust as needed
        for entity in all_entities:
            if entity != self:
                for x in range(self.x - check_distance, self.x + check_distance + 1):
                    for y in range(self.y - check_distance, self.y + check_distance + 1):
                        if (x, y) in entity.trail:
                            nearby_trails.append(((x, y), entity))
                            break
                    if nearby_trails:
                        break
        return nearby_trails


    def target_nearby_trail(self, target):
        dx = target[0] - self.x
        dy = target[1] - self.y
        if random.choice([True, False]):  # Randomly choose horizontal or vertical movement
            self.set_direction((1 if dx > 0 else -1, 0) if dx != 0 else (0, 1 if dy > 0 else -1))
        else:
            self.set_direction((0, 1 if dy > 0 else -1) if dy != 0 else (1 if dx > 0 else -1, 0))


    def find_nearest_entity(self, all_entities):
        nearest_distance = float('inf')
        for entity in all_entities:
            if entity != self:
                dist = ((self.x - entity.x) ** 2 + (self.y - entity.y) ** 2) ** 0.5
                if dist < nearest_distance:
                    nearest_distance = dist
        return nearest_distance


    def is_about_to_trap_itself(self):
        if not self.direction:
            return False
        
        next_pos = (self.x + self.direction[0], self.y + self.direction[1])
        if not self.is_valid_move(*next_pos):
            return True
        
        # Check if the next move would leave only one exit
        exits = sum(1 for dx, dy in [(0, 1), (1, 0), (0, -1), (-1, 0)]
                    if self.is_valid_move(next_pos[0] + dx, next_pos[1] + dy))
        return exits <= 1

    """
    def is_valid_move(self, x, y):
        return (0 <= x < GRID_SIZE and 0 <= y < GRID_SIZE and 
                (x, y) not in self.trail)

    def is_safe_move(self, x, y):
        return self.is_valid_move(x, y)
    """

    def check_potential_collision(self):
        # Check for potential head-on collisions
        if (self.x, self.y) not in self.territory:
            for entity in all_entities:
                if entity != self and abs(entity.x - self.x) <= 1 and abs(entity.y - self.y) <= 1:
                    return True
        return False


    def avoid_collision(self):
        directions = [(0, 1), (1, 0), (0, -1), (-1, 0)]
        random.shuffle(directions)
        for dx, dy in directions:
            new_x, new_y = self.x + dx, self.y + dy
            if self.is_valid_move(new_x, new_y) and not self.check_potential_collision():
                self.set_direction((dx, dy))
                return
        self.moving = False


    def is_far_from_territory(self, threshold=10):
        return min((abs(self.x - tx) + abs(self.y - ty) for tx, ty in self.territory), default=0) > threshold


    def find_expansion_target(self):
        max_distance = 5
        possible_targets = []
        for dx in range(-max_distance, max_distance + 1):
            for dy in range(-max_distance, max_distance + 1):
                x, y = self.x + dx, self.y + dy
                if self.is_safe_move(x, y) and (x, y) not in self.territory:
                    possible_targets.append((x, y))
        return random.choice(possible_targets) if possible_targets else None


    """
    def is_near_border(self, x, y, distance=2):
        return (x < distance or x >= GRID_SIZE - distance or 
                y < distance or y >= GRID_SIZE - distance)
    """

    def return_to_territory(self):
        target = self.find_nearest_territory_edge()
        if target:
            path = self.bfs_path_to_target(target)
            if path and len(path) > 1:
                next_step = path[1]
                if self.is_valid_orthogonal_move(self.x, self.y, next_step[0], next_step[1]) and self.is_safe_move(next_step[0], next_step[1]):
                    self.set_direction((next_step[0] - self.x, next_step[1] - self.y))
                    return True
        return False


    def bot_expand_territory(self):
        target = self.find_expansion_target()
        if target:
            path = self.bfs_path_to_target(target)
            if path and len(path) > 1:
                next_step = path[1]
                if self.is_valid_orthogonal_move(self.x, self.y, next_step[0], next_step[1]) and self.is_safe_move(next_step[0], next_step[1]):
                    self.set_direction((next_step[0] - self.x, next_step[1] - self.y))
                    return True
        self.change_direction_randomly()
        return True



    def find_best_path(self):
        player = next(entity for entity in all_entities if isinstance(entity, Player) and not isinstance(entity, Bot))
        
        # Always consider returning to territory if trail is too long
        if len(self.trail) > self.max_trail_length:
            return self.return_to_territory()

        # Look for nearby trails with adjusted priorities
        nearby_trails = self.find_nearby_trails()
        for trail, owner in nearby_trails:
            aggression = self.calculate_aggression(owner)
            if random.random() < aggression:
                return self.move_towards_trail(trail)

        # If no trails to pursue, consider expanding or moving towards the player
        if self.distance_to(player) <= PROXIMITY_THRESHOLD and random.random() < self.calculate_aggression(player):
            return self.move_towards_entity(player)
        else:
            return self.bot_expand_territory()


    def move_towards_trail(self, trail):
        dx = trail[0] - self.x
        dy = trail[1] - self.y
        if abs(dx) > abs(dy):
            new_x = self.x + (1 if dx > 0 else -1)
            if self.is_safe_move(new_x, self.y):
                self.set_direction((1 if dx > 0 else -1, 0))
                return True
        else:
            new_y = self.y + (1 if dy > 0 else -1)
            if self.is_safe_move(self.x, new_y):
                self.set_direction((0, 1 if dy > 0 else -1))
                return True
        return False


    def move_towards_entity(self, entity):
        path = self.bfs_path_to_target((entity.x, entity.y))
        if path and len(path) > 1:
            next_step = path[1]
            if self.is_valid_orthogonal_move(self.x, self.y, next_step[0], next_step[1]) and self.is_safe_move(next_step[0], next_step[1]):
                self.set_direction((next_step[0] - self.x, next_step[1] - self.y))
                return True
        return False



    def is_in_narrow_space(self):
        # Check if the bot is in a 1-tile wide space between territory and border
        for dx, dy in [(0, 1), (1, 0), (0, -1), (-1, 0)]:
            if (self.x + dx, self.y + dy) in self.territory:
                opposite_x, opposite_y = self.x - dx, self.y - dy
                if self.is_border_tile(opposite_x, opposite_y):
                    return True
        return False


    def escape_narrow_space(self):
        # Try to move along the narrow space
        for dx, dy in [(0, 1), (1, 0), (0, -1), (-1, 0)]:
            new_x, new_y = self.x + dx, self.y + dy
            if self.is_valid_move(new_x, new_y) and not self.is_in_narrow_space():
                self.set_direction((dx, dy))
                return
        
        # If can't escape, move towards own territory
        for dx, dy in [(0, 1), (1, 0), (0, -1), (-1, 0)]:
            if (self.x + dx, self.y + dy) in self.territory:
                self.set_direction((dx, dy))
                return
        
        # If all else fails, try to move randomly
        self.change_direction_randomly()


    def find_nearest_territory_edge(self):
        if (self.x, self.y) in self.territory:
            return self.find_territory_exit()

        queue = deque([(self.x, self.y, 0)])
        visited = set()

        while queue:
            x, y, dist = queue.popleft()
            if (x, y) in visited:
                continue
            visited.add((x, y))

            if (x, y) in self.territory:
                return (x, y)

            for dx, dy in [(0, 1), (1, 0), (0, -1), (-1, 0)]:
                nx, ny = x + dx, y + dy
                if self.is_valid_move(nx, ny):
                    queue.append((nx, ny, dist + 1))

        return None


    def find_territory_exit(self):
        for dx, dy in [(0, 1), (1, 0), (0, -1), (-1, 0)]:
            nx, ny = self.x + dx, self.y + dy
            if self.is_valid_move(nx, ny) and (nx, ny) not in self.territory:
                return (nx, ny)
        return None


    def bfs_path_to_target(self, target):
        queue = deque([(self.x, self.y)])
        visited = set([(self.x, self.y)])
        parent = {}

        while queue:
            x, y = queue.popleft()
            if (x, y) == target:
                path = []
                while (x, y) != (self.x, self.y):
                    path.append((x, y))
                    x, y = parent[(x, y)]
                path.append((self.x, self.y))
                return path[::-1]

            for dx, dy in [(0, 1), (1, 0), (0, -1), (-1, 0)]:
                nx, ny = x + dx, y + dy
                if self.is_safe_move(nx, ny) and (nx, ny) not in visited and self.is_valid_orthogonal_move(x, y, nx, ny):
                    queue.append((nx, ny))
                    visited.add((nx, ny))
                    parent[(nx, ny)] = (x, y)

        return None


    def change_direction_randomly(self):
        directions = [(0, 1), (1, 0), (0, -1), (-1, 0)]
        random.shuffle(directions)
        for direction in directions:
            new_x, new_y = self.x + direction[0], self.y + direction[1]
            if self.is_valid_move(new_x, new_y):
                self.set_direction(direction)
                return
        self.moving = False


    def move_towards_center(self):
        center_x, center_y = GRID_SIZE // 2, GRID_SIZE // 2
        dx = center_x - self.x
        dy = center_y - self.y
        if abs(dx) > abs(dy):
            self.set_direction((1 if dx > 0 else -1, 0))
        else:
            self.set_direction((0, 1 if dy > 0 else -1))


    def change_direction(self):
        possible_directions = [(0, -1), (0, 1), (-1, 0), (1, 0)]
        if self.direction:
            opposite = (-self.direction[0], -self.direction[1])
            if opposite in possible_directions:
                possible_directions.remove(opposite)
        new_direction = random.choice(possible_directions)
        self.set_direction(new_direction)
        # print(f"Bot changed direction to {self.direction}")



    def avoid_own_trail(self):
        if not self.direction:
            # print(f"Bot at ({self.x}, {self.y}) has no direction")
            return

        # Look ahead for potential collisions
        for i in range(1, 4):  # Look up to 3 steps ahead
            next_pos = (self.x + self.direction[0] * i, self.y + self.direction[1] * i)
            # print(f"Bot at ({self.x}, {self.y}) checking future position {next_pos}")
            
            if next_pos in self.trail or not (0 <= next_pos[0] < GRID_SIZE and 0 <= next_pos[1] < GRID_SIZE):
                # print(f"Bot at ({self.x}, {self.y}) detected potential collision at {next_pos}")
                self.change_direction_to_avoid_collision()
                return

        # print(f"Bot at ({self.x}, {self.y}) path is clear for the next 3 steps")


    def change_direction_to_avoid_collision(self):
        current_direction = self.direction
        possible_directions = [(0, 1), (1, 0), (0, -1), (-1, 0)]
        possible_directions.remove((-current_direction[0], -current_direction[1]))  # Remove opposite direction
        
        for new_direction in possible_directions:
            if self.is_safe_direction(new_direction):
                self.set_direction(new_direction)
                # print(f"Bot at ({self.x}, {self.y}) changed direction to {new_direction}")
                return
        
        # print(f"Bot at ({self.x}, {self.y}) couldn't find a safe direction")


    def is_safe_direction(self, direction):
        for i in range(1, 4):  # Check 3 steps ahead
            next_pos = (self.x + direction[0] * i, self.y + direction[1] * i)
            if next_pos in self.trail or not (0 <= next_pos[0] < GRID_SIZE and 0 <= next_pos[1] < GRID_SIZE):
                return False
        return True


    def check_direction(self, direction):
        current_pos = (self.x, self.y)
        steps = 0
        while steps < 10:  # Limit the number of steps to check
            next_pos = (current_pos[0] + direction[0], current_pos[1] + direction[1])
            # print(f"Checking position {next_pos}")
            if next_pos in self.trail or not (0 <= next_pos[0] < GRID_SIZE and 0 <= next_pos[1] < GRID_SIZE):
                # print(f"Hit trail or boundary at {next_pos}")
                return False
            if next_pos in self.territory:
                # print(f"Reached territory at {next_pos}")
                return True
            current_pos = next_pos
            steps += 1
        # print("Reached step limit without finding territory or obstacle")
        return True


    def set_direction(self, new_direction):
        if not self.moving:
            self.direction = new_direction
            self.moving = True
        elif (self.x, self.y) in self.territory:
            self.direction = new_direction
        else:
            if not self.is_opposite_direction(new_direction):
                self.direction = new_direction
        
        if self.direction:
            self.last_direction = self.direction

#------------------------------------------------------------------------------------------

def respawn_bot(dead_bot, existing_entities):
    x, y = find_valid_spawn_position(existing_entities)
    new_bot = Bot(x, y)
    return new_bot
#------------------------------------------------------------------------------------------------------------------------------------

class ScoreManager:
    def __init__(self):
        self.scores = {}
        self.greek_letters = ['alpha', 'beta', 'gamma', 'delta', 'epsilon', 'zeta', 'eta', 'theta', 'iota', 'kappa', 
                              'lambda', 'mu', 'nu', 'xi', 'omicron', 'pi', 'rho', 'sigma', 'tau', 'upsilon', 
                              'phi', 'chi', 'psi', 'omega']
        self.current_letter_index = 0
        self.current_number = 1

    def generate_bot_name(self):
        name = f"{self.greek_letters[self.current_letter_index]}{self.current_number}"
        self.current_letter_index += 1
        if self.current_letter_index >= len(self.greek_letters):
            self.current_letter_index = 0
            self.current_number += 1
        return name

    def initialize_score(self, entity):
        if isinstance(entity, Bot):
            name = f"{self.generate_bot_name()}_{entity.id}"
        else:
            name = f"Player_{entity.id}"
        entity.name = name
        self.scores[name] = 25  # Starting score, from 5x5 starting-territory


    def update_score(self, entity):
        self.scores[entity.name] = len(entity.territory)

    def add_kill_score(self, killer):
        self.scores[killer.name] += 50

    def reset_bot_score(self, bot):
        self.scores[bot.name] = 25

    def get_top_25_scores(self):
        return sorted(self.scores.items(), key=lambda x: x[1], reverse=True)[:25]

#------------------------------------------------------------------------------------------------------------------------------------------------------------------
# Modify the draw_score_table function
def draw_score_table(screen, score_manager, entities):
    global last_score_update_time, cached_score_surface, last_scores
    current_time = time.time()
    
    if current_time - last_score_update_time > 0.5 or cached_score_surface is None:
        font = pygame.font.Font(None, 24)
        top_scores = score_manager.get_top_25_scores()
        
        if cached_score_surface is None:
            table_width = 250
            table_height = min(len(top_scores) * 25 + 30, 655)
            cached_score_surface = pygame.Surface((table_width, table_height))
            cached_score_surface.fill((0, 0, 0))  # Black background
            
            # Draw headers
            header_color = (255, 255, 255)  # White color for headers
            name_header = font.render("Name", True, header_color)
            score_header = font.render("Score", True, header_color)
            cached_score_surface.blit(name_header, (10, 5))
            cached_score_surface.blit(score_header, (table_width - 60, 5))

            # Draw horizontal line under headers
            pygame.draw.line(cached_score_surface, header_color, (0, 25), (table_width, 25))

        for i, (name, score) in enumerate(top_scores):
            y = 35 + i * 25
            
            # Check if score has changed or is new
            if name not in last_scores or last_scores[name] != score:
                # Determine the color based on the entity type
                if name.startswith("Player"):
                    color = GREEN_100
                else:
                    # Find the corresponding bot
                    bot = next((b for b in bots if b.name == name), None)
                    color = bot.color if bot else (200, 200, 200)  # Default color if bot not found

                # Clear the previous score
                pygame.draw.rect(cached_score_surface, (0, 0, 0), (10, y, 230, 25))

                # Render and blit the new name and score
                name_surface = font.render(name, True, color)
                score_surface = font.render(str(score), True, color)
                cached_score_surface.blit(name_surface, (10, y))
                cached_score_surface.blit(score_surface, (240 - score_surface.get_width(), y))

                # Update the last_scores dictionary
                last_scores[name] = score

        # Remove entries from last_scores that are no longer in top_scores
        current_names = set(name for name, _ in top_scores)
        last_scores = {name: score for name, score in last_scores.items() if name in current_names}

        last_score_update_time = current_time

    screen.blit(cached_score_surface, (WINDOW_WIDTH - cached_score_surface.get_width() - 10, SHRUNKEN_RADAR_SIZE + 10))

"""
def ensure_contrasting_color(color, bg_color):
    # Calculate luminance of the color and background
    color_luminance = (0.299 * color[0] + 0.587 * color[1] + 0.114 * color[2]) / 255
    bg_luminance = (0.299 * bg_color[0] + 0.587 * bg_color[1] + 0.114 * bg_color[2]) / 255

    if abs(color_luminance - bg_luminance) < 0.5:  # If the contrast is too low
        # Invert the color
        return tuple(255 - c for c in color)
    return color
"""

def draw_radar(screen, territories):
    radar = pygame.Surface((SHRUNKEN_RADAR_SIZE, SHRUNKEN_RADAR_SIZE))
    radar.fill(RADAR_BACKGROUND_COLOR)
    radar_scale = SHRUNKEN_RADAR_SIZE / GRID_SIZE

    # Draw all territories on radar
    for entity, territory in territories.items():
        for x, y in territory:
            pygame.draw.rect(radar, RADAR_TERRITORY_COLOR,
                             (int(x * radar_scale), int(y * radar_scale),
                              max(1, int(radar_scale)), max(1, int(radar_scale))))

    # Add a border to the radar
    pygame.draw.rect(radar, (0, 0, 0), radar.get_rect(), 1)

    # Calculate the new position for the radar
    radar_x = VIEWPORT_SIZE + RADAR_SHRINK
    radar_y = 0  # Keep it at the top of the screen

    # Blit the radar onto the screen at the new position
    screen.blit(radar, (radar_x, radar_y))


def draw_viewport_border(screen, offset_x, offset_y):
    border_color = (0, 0, 0)  # Black for the viewport frame
    border_width = 2
    pygame.draw.rect(screen, border_color, (0, 0, VIEWPORT_SIZE, VIEWPORT_SIZE), border_width)

    bright_red = (200, 0, 0)
    border_line_width = 2

    # Calculate and draw only the visible borders
    left_visible = offset_x <= 1
    right_visible = offset_x + VIEWPORT_TILES >= GRID_SIZE - 1
    top_visible = offset_y <= 1
    bottom_visible = offset_y + VIEWPORT_TILES >= GRID_SIZE - 1

    if top_visible:
        y_pos = max(0, 1 - offset_y) * TILE_SIZE
        pygame.draw.line(screen, bright_red, (0, y_pos), (VIEWPORT_SIZE, y_pos), border_line_width)
    
    if bottom_visible:
        y_pos = min(VIEWPORT_SIZE, (GRID_SIZE - 1 - offset_y) * TILE_SIZE)
        pygame.draw.line(screen, bright_red, (0, y_pos), (VIEWPORT_SIZE, y_pos), border_line_width)
    
    if left_visible:
        x_pos = max(0, 1 - offset_x) * TILE_SIZE
        pygame.draw.line(screen, bright_red, (x_pos, 0), (x_pos, VIEWPORT_SIZE), border_line_width)
    
    if right_visible:
        x_pos = min(VIEWPORT_SIZE, (GRID_SIZE - 1 - offset_x) * TILE_SIZE)
        pygame.draw.line(screen, bright_red, (x_pos, 0), (x_pos, VIEWPORT_SIZE), border_line_width)


# Initialize game state -------------------------------------------------------------------------------------------------------------------------------------------
player_x, player_y = find_valid_spawn_position([])  # Empty list as there are no existing entities yet
player = Player(player_x, player_y, GREEN_100)
bots = []
all_entities = [player]

for i in range(NUM_BOTS):
    x, y = find_valid_spawn_position(all_entities)
    bot = Bot(x, y)
    bots.append(bot)
    all_entities.append(bot)


# Initialize the ScoreManager
score_manager = ScoreManager()


# Create a dictionary to store all territories
territories = {entity: entity.territory for entity in all_entities}


def resolve_territory_conflicts():
    for entity in all_entities:
        entity.territory = set(pos for pos in entity.territory if all(pos not in other.territory for other in all_entities if other != entity))


for entity in all_entities:
    score_manager.initialize_score(entity)


# Main game loop --------------------------------------------------------------------------------------------------------------------------------------------------
running = True
clock = pygame.time.Clock()

while running:
    frame_counter += 1  # Increment the frame counter each iteration
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                running = False
            elif event.key in (pygame.K_UP, pygame.K_DOWN, pygame.K_LEFT, pygame.K_RIGHT):
                if game_paused:
                    game_paused = False
                    print("Game resumed!")
                elif not game_started:
                    game_started = True
                    print("Game started!")
                player.moving = True
                if event.key == pygame.K_UP:
                    player.set_direction((0, -1))
                elif event.key == pygame.K_DOWN:
                    player.set_direction((0, 1))
                elif event.key == pygame.K_LEFT:
                    player.set_direction((-1, 0))
                elif event.key == pygame.K_RIGHT:
                    player.set_direction((1, 0))
            elif event.key == pygame.K_p:
                player.moving = False
            elif event.key == pygame.K_h:
                game_paused = not game_paused
                if game_paused:
                    print("Game paused. Press any arrow key to resume.")
                else:
                    print("Game resumed!")
            elif event.key == pygame.K_s:
                game_paused = True
                save_game(player, bots, score_manager, territories)
                print("Game saved and paused. Press any arrow key to resume.")
            elif event.key == pygame.K_l:
                loaded_state = load_game()
                if loaded_state:
                    player, bots, score_manager, territories = loaded_state
                    all_entities = [player] + bots
                    game_started = True
                    game_paused = True
                    print("Game loaded and paused. Press any arrow key to resume.")

    #--------------------------------------------------------------------------------------
    # After the event handling, in your main game loop:
    if not game_paused and game_started:       
        if frame_counter % 2 == 0:  # Only move on even frames
            # Update game state
            for entity in all_entities:
                entity.move()


        # Handle territory expansion and conflicts
        for entity in all_entities:
            if (entity.x, entity.y) in entity.territory:
                entity.expand_territory()
            
            # Update the territories dictionary
            territories[entity] = entity.territory

        # Resolve territory conflicts
        for entity in all_entities:
            entity.territory = set(pos for pos in entity.territory if all(pos not in other.territory or other == entity for other in all_entities))
            territories[entity] = entity.territory


        # After moving all entities
        color_count = {}
        for entity in all_entities:
            if entity.color in color_count:
                pass
                # print(f"Warning: Duplicate color {entity.color} found for entities {color_count[entity.color]} and {entity.name}")
            else:
                color_count[entity.color] = entity.name


        # Check for collisions
        entities_to_remove = []
        for entity in all_entities:
            # Check for self-collision or entering lethal zone
            if entity.check_collision_with_trail(entity.trail[:-1]) or entity.is_in_lethal_zone(entity.x, entity.y):
                entities_to_remove.append(entity)
            else:
                # Check for collision with other entities' trails
                collided_with = entity.check_collision_with_others_trail(all_entities)
                if collided_with:
                    entities_to_remove.append(collided_with)  # The owner of the trail dies
                    score_manager.add_kill_score(entity)  # The entity that hit the trail gets the kill score



        # Handle head-on collisions
        for i, entity1 in enumerate(all_entities):
            for entity2 in all_entities[i+1:]:
                if (entity1.x, entity1.y) == (entity2.x, entity2.y):
                    entity1_in_territory = entity1.is_in_own_territory()
                    entity2_in_territory = entity2.is_in_own_territory()

                    if entity1_in_territory and entity2_in_territory:
                        # Both entities are in their own territory, just block the move
                        entity1.x, entity1.y = entity1.trail[-2] if len(entity1.trail) > 1 else (entity1.x, entity1.y)
                        entity2.x, entity2.y = entity2.trail[-2] if len(entity2.trail) > 1 else (entity2.x, entity2.y)
                    elif entity1_in_territory:
                        # Entity1 survives, Entity2 is removed
                        entities_to_remove.append(entity2)
                        score_manager.add_kill_score(entity1)
                    elif entity2_in_territory:
                        # Entity2 survives, Entity1 is removed
                        entities_to_remove.append(entity1)
                        score_manager.add_kill_score(entity2)
                    else:
                        # Neither entity is in their own territory, both are removed
                        entities_to_remove.extend([entity1, entity2])
                        # print(f"Head-on collision in open space between {entity1.name} and {entity2.name}")
                        # No score is awarded in this case

        # Remove duplicates from entities_to_remove
        entities_to_remove = list(set(entities_to_remove))

        # Handle removals and respawns
        for entity in entities_to_remove:
            if entity in bots:
                bots.remove(entity)
                all_entities.remove(entity)
                del territories[entity]
                del score_manager.scores[entity.name]  # Remove the score when the entity is removed
                new_bot = respawn_bot(entity, all_entities)
                bots.append(new_bot)
                all_entities.append(new_bot)
                territories[new_bot] = new_bot.territory
                score_manager.initialize_score(new_bot)
            elif entity == player:
                print("Player removed! Game over.")
                running = False
                break


        # In the main game loop, after moving entities and checking collisions
        for entity in all_entities:
            score_manager.update_score(entity)

    # -------------------------------------------------------------------------------------------
    # Update territories
    for entity in all_entities:
        if entity.is_in_own_territory():
            entity.expand_territory()
        territories[entity] = entity.territory
    # -------------------------------------------------------------------------------------------------------------------------------------------------------------
    # Calculate viewport offset
    # offset_x = max(0, min(player.x - VIEWPORT_TILES // 2, GRID_SIZE - VIEWPORT_TILES - 1))
    # offset_y = max(0, min(player.y - VIEWPORT_TILES // 2, GRID_SIZE - VIEWPORT_TILES - 1))
    offset_x = max(1, min(player.x - VIEWPORT_TILES // 2, GRID_SIZE - VIEWPORT_TILES - 1))
    offset_y = max(1, min(player.y - VIEWPORT_TILES // 2, GRID_SIZE - VIEWPORT_TILES - 1))
    # -------------------------------------------------------------------------------------------------
    # Draw everything
    screen.fill(BACKGROUND_COLOR)

    # Draw viewport
    viewport = pygame.Surface((VIEWPORT_SIZE, VIEWPORT_SIZE))

    # 1. Draw the dark grey background
    viewport.fill(BACKGROUND_COLOR)

    # 2. Draw all territories
    for entity, territory in territories.items():
        for x, y in territory:
            if offset_x <= x < offset_x + VIEWPORT_TILES and offset_y <= y < offset_y + VIEWPORT_TILES:
                pygame.draw.rect(viewport, entity.color, ((x - offset_x) * TILE_SIZE, (y - offset_y) * TILE_SIZE, TILE_SIZE, TILE_SIZE))

    # 3. Draw the black grid-lines
    for i in range(VIEWPORT_TILES + 1):
        pygame.draw.line(viewport, GRID_COLOR, (i * TILE_SIZE, 0), (i * TILE_SIZE, VIEWPORT_SIZE - 1))
        pygame.draw.line(viewport, GRID_COLOR, (0, i * TILE_SIZE), (VIEWPORT_SIZE - 1, i * TILE_SIZE))

    # 4. Draw the trails for all entities (player and bots)
    for entity in all_entities:
        trail_color = TRAIL_COLOR if entity == player else entity.color
        for x, y in entity.trail:
            if offset_x <= x < offset_x + VIEWPORT_TILES and offset_y <= y < offset_y + VIEWPORT_TILES:
                pygame.draw.rect(viewport, trail_color, ((x - offset_x) * TILE_SIZE, (y - offset_y) * TILE_SIZE, TILE_SIZE, TILE_SIZE))

    # 5. Draw all entities (player and bots)
    for entity in all_entities:
        entity.draw(viewport, offset_x, offset_y)
    # --------------------------------------------------------------
    # Draw viewport & borders on main screen
    screen.blit(viewport, (0, 0))

    draw_viewport_border(screen, offset_x, offset_y)
    # ----------------------------------------------------------------------------------------------------------------------------------------------------
    draw_radar(screen, territories)
    # screen.blit(radar, (VIEWPORT_SIZE, 0))

    draw_score_table(screen, score_manager, all_entities)

    if not game_started:
        font = pygame.font.Font(None, 36)
        text = font.render("Press an arrow key to start", True, (255, 255, 255))
        text_rect = text.get_rect(center=(WINDOW_WIDTH//2, WINDOW_HEIGHT//2))
        screen.blit(text, text_rect)


    pygame.display.flip()
    # clock.tick(10)  # Limit to 10 FPS for easier testing
    clock.tick(30)

pygame.quit()


