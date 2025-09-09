import random
from collections import deque

class PlayerState:
    def __init__(self, user_id, username):
        self.user_id = user_id
        self.username = username
        self.x = 20
        self.y = 0
        self.vy = 0
        self.alive = True
        self.score = 0
        self.jump_cool = 0

class Obstacle:
    def __init__(self, x):
        self.x = x
        self.w = 16
        self.h = random.choice([20,30])

class GameSession:
    def __init__(self, chat_id, session_id, players:list):
        self.chat_id = chat_id
        self.session_id = session_id
        self.players = [PlayerState(uid, uname) for uid,uname in players]
        self.obstacles = deque()
        self.tick = 0
        self.speed = 4.0
        self.running = False
        self.finish_x = 1200
        self.winner = None
        self._spawn_timer = 0

    def start(self):
        self.running = True
        self.tick = 0
        for p in self.players:
            p.x = 20
            p.y = 0
            p.alive = True
            p.score = 0
        self.obstacles.clear()
        self._spawn_timer = 30

    def jump(self, player_index:int):
        p = self.players[player_index]
        if not p.alive: return
        if p.jump_cool>0: return
        p.vy = -9
        p.jump_cool = 6

    def update(self):
        self.tick += 1
        self.speed += 0.002  # gradually increase speed

        # spawn obstacles
        self._spawn_timer -= 1
        if self._spawn_timer <= 0:
            self._spawn_timer = random.randint(30,60)
            obs_x = max([o.x for o in self.obstacles], default=200) + random.randint(120,260)
            self.obstacles.append(Obstacle(obs_x))

        # move obstacles
        for o in list(self.obstacles):
            o.x -= self.speed
            if o.x + o.w < 0:
                self.obstacles.popleft()

        # update players
        for p in self.players:
            if not p.alive: continue
            p.x += self.speed * 0.6
            p.vy += 0.8
            p.y += p.vy
            if p.y > 0:
                p.y = 0
                p.vy = 0
            if p.jump_cool>0:
                p.jump_cool -= 1
            # collision check
            for o in self.obstacles:
                if abs(p.x - o.x) < (o.w+10) and p.y >= 0:
                    p.alive = False
            p.score = int(p.x)
            if p.x >= self.finish_x and not self.winner:
                self.winner = p
                self.running = False

        if all(not p.alive for p in self.players):
            self.running = False

        states = [{'x': int(p.x/(self.finish_x/700)), 'y': int(-p.y), 'alive': p.alive} for p in self.players]
        scores = {i: self.players[i].score for i in range(len(self.players))}
        return {'tick': self.tick, 'states': states, 'scores': scores, 'winner': self.winner.username if self.winner else None}
