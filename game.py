# game.py
import random
from collections import deque

class PlayerState:
    def __init__(self, user_id:int, username:str):
        self.user_id = user_id
        self.username = username
        self.x = 0.0   # world progress
        self.y = 0.0   # vertical offset, 0 = on ground; negative when jumping (so render uses -y)
        self.vy = 0.0
        self.alive = True
        self.score = 0
        self.jump_cool = 0

class Obstacle:
    def __init__(self, x:float, w:int=16, h:int=28):
        self.x = x
        self.w = w
        self.h = h

class GameSession:
    def __init__(self, chat_id:int, session_id:str, players:list, max_players:int=3, finish_x:int=1600):
        """
        players: list of (user_id, username) tuples
        """
        self.chat_id = chat_id
        self.session_id = session_id
        self.players = [PlayerState(uid, uname) for uid, uname in players]
        self.max_players = max_players
        self.finish_x = finish_x
        self.obstacles = deque()
        self.tick = 0
        self.speed = 6.0  # base player-forward speed per tick (world units)
        self.running = False
        self.winner = None
        self._spawn_timer = 20
        self.creator_id = players[0][0] if players else None

    def add_player(self, user_id:int, username:str):
        if any(p.user_id == user_id for p in self.players):
            return False, "already"
        if len(self.players) >= self.max_players:
            return False, "full"
        self.players.append(PlayerState(user_id, username))
        return True, None

    def remove_player(self, user_id:int):
        for p in self.players:
            if p.user_id == user_id:
                self.players.remove(p)
                return True
        return False

    def start(self):
        self.running = True
        self.tick = 0
        self.obstacles.clear()
        self._spawn_timer = 20
        # reset players
        for i,p in enumerate(self.players):
            p.x = 20 + i*4
            p.y = 0
            p.vy = 0
            p.alive = True
            p.score = 0
            p.jump_cool = 0
        self.winner = None
        self.speed = 5.0

    def jump_by_user(self, user_id:int):
        idx = None
        for i,p in enumerate(self.players):
            if p.user_id == user_id:
                idx = i
                break
        if idx is None:
            return False, "not_in_game"
        p = self.players[idx]
        if not p.alive:
            return False, "dead"
        if p.jump_cool > 0:
            return False, "cooldown"
        # apply jump impulse
        p.vy = -11.5
        p.jump_cool = 6
        return True, None

    def update(self):
        """
        Advance one tick; updates physics, spawns obstacles, collision, returns state dict.
        """
        self.tick += 1

        # spawn obstacles ahead of the farthest player
        self._spawn_timer -= 1
        if self._spawn_timer <= 0:
            farthest = max((p.x for p in self.players), default=0)
            new_x = max(farthest + random.randint(120, 260), farthest + 120)
            new_h = random.choice([20, 26, 34])
            new_w = random.choice([12, 16, 20])
            self.obstacles.append(Obstacle(new_x, w=new_w, h=new_h))
            self._spawn_timer = random.randint(20, 50)

        # physics & collisions
        for p in self.players:
            if not p.alive:
                continue
            # forward progress
            p.x += self.speed * 0.6
            # gravity
            p.vy += 0.9
            p.y += p.vy
            if p.y > 0:
                p.y = 0
                p.vy = 0
            if p.jump_cool > 0:
                p.jump_cool -= 1

            # collision detection
            for o in list(self.obstacles):
                # if player's world x overlaps obstacle x
                # consider small bounding boxes: player width ~ 24
                if (p.x + 6) >= o.x and (p.x - 6) <= (o.x + o.w):
                    # if player is on ground (y >= 0) => collision
                    if p.y >= 0:
                        p.alive = False

            p.score = int(p.x)

            # check finish
            if p.x >= self.finish_x and not self.winner:
                self.winner = p
                self.running = False

        # remove obstacles behind all players
        min_player_x = min((p.x for p in self.players), default=0)
        while self.obstacles and (self.obstacles[0].x + 40) < (min_player_x - 40):
            self.obstacles.popleft()

        # speed ramp up slowly
        self.speed = min(self.speed + 0.003, 12.0)

        if all(not p.alive for p in self.players):
            self.running = False

        # prepare return state
        states = []
        for p in self.players:
            states.append({
                'x': p.x,
                'y': p.y,
                'alive': p.alive,
                'username': p.username,
                'score': p.score
            })
        obs_list = [{'x': o.x, 'w': o.w, 'h': o.h} for o in self.obstacles]
        return {'tick': self.tick, 'states': states, 'scores': {i: self.players[i].score for i in range(len(self.players))}, 'winner': (self.winner.username if self.winner else None), 'obstacles': obs_list}
