import os, sys
from collections import deque
from pygame.locals import *
from cube import *
from algo import Imported_Algo, Rule_Lookup
import datetime
from helper import Formatter
from persist import Persist
import time
from datetime import datetime
import random

class Solver():
	def __init__(self):
		self.persist = Persist()
		pass

	def solve(self, algo_name, scramble):
		c = Cube()	
		
		dbalgo = self.persist.get_algo(algo_name)

		algo = Imported_Algo(c, dbalgo)

		move_cnt = 0	
		solution = []
		print scramble
		for move in scramble.split(' '):
			c.rotate([move])

		done = False
		success = False
		t0 = time.time()
		while True:

			fst = True
			while len(algo.queued_moves) > 0 or fst:
				fst = False
				move = algo.next_move()
				if move == 'fail':
					done = True

				if move != None and move != ' ' and move != '' and move != 'fail':
					move_cnt += 1
					c.rotate([move])
					solution.append(move)
					
			if len(algo.algo_steps) == 0:
				done = True
				success = True

			else:	
				step = algo.algo_steps[0]

				if step['type'] == 'comment':
					print "Comment:", step['value']
					if step['value'] == "done":
							
						done = True
						success = True
			
			if done:
				break
			#next step in algo		
			res = algo.parse_algo()

		result = {'scramble' : scramble,
			'move_cnt' : move_cnt,
			'success' : success,
			'rules' : algo.rules,
			'moves' : solution,
			'name' : algo_name,
			'date' : datetime.now(),
			'time' : time.time() - t0,
			'search_cnt' : algo.search_cnt,
			'rnd' : random.randrange(0,1000000000000)}
	
		return result

