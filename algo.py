from cube import *
from collections import deque
import random
from copy import copy, deepcopy
import time, datetime

SEARCH_LIMIT = 10000

#enum types for readability
class Orientation:
	any = 0
	oriented = 1
	non_oriented = 2

class Edge:
	outer = 0
	center = 1

class Block:
	inner_1x1 = 0 
	inner_2x1 = 1
	inner_2x2 = 2
	inner_3x1 = 3
	inner_3x3 = 4
	inner_3x2 = 5
	inner_1x1_corner = 6

Rule_Lookup = {
		0 : 'inner_1x1',
		1 : 'inner_2x1',
		2 : 'inner_2x2',
		3 : 'inner_3x1',
		4 : 'inner_3x3',
		5 : 'inner_3x2',
		6 : 'inner_1x1_corner'
	}
Rule_Lookup_Reversed = {}
for key, value in Rule_Lookup.items():
	Rule_Lookup_Reversed[value] = key
piece = {
		'Outer' : Edge.outer,
		'Center' : Edge.center
		}
Piece_Lookup = {}
for key, value in piece.items():
	Piece_Lookup[value] = key

orientation = { 'Any' : Orientation.any,
		'Oriented' : Orientation.oriented,
		'Non_Oriented' : Orientation.non_oriented
		}
Orientation_Lookup = {}
for key, value in orientation.items():
	Orientation_Lookup[value] = key

class Imported_Algo():

	def __init__(self, cube, algo_json):
		self.cube = cube
		self.algo_steps = deque()
		for step in algo_json['commands']:
			self.algo_steps.append(step)	
		self.allowed_sequences = []
		self.rules = []#active rules
		self.queued_moves = deque()
	
		#build patterns to recognize
		self.inner_1x1 = [[7],[11],[13],[17]]
		self.inner_2x1 = [[6,7], [7,8], [8,13], [13,18], [6,11], [11,16],[16,17],[17,18]]
		self.inner_2x2 = [[6,7,11], [7,8,13], [11,16,17], [13,17,18]]
		self.inner_3x1 = [[6,7,8],[6,11,16],[16,17,18],[8,13,18]]
		self.inner_3x3 = [[6,7,8,11,13,16,17,18]]
		self.inner_3x2 = []
		self.inner_1x1_corner = [[6],[8],[16],[18]]

		#building the 3x2 blocks are easier like this
		for sub in self.inner_3x1:
			tmp = []
			tmp.extend(self.inner_3x3[0])

			for c in sub:
				tmp.remove(c)
			self.inner_3x2.append(tmp)

		self.stored = 0 #stored edges when building them
		self.cross = 0 #bottom cross for 3x3 solve
		self.pairs = 0
		self.search_cnt = 0

	def get_remaining_steps(self):
		return self.algo_steps

	#continue parsing the algorithm lines
	def parse_algo(self):
		while True:
			step = self.algo_steps.popleft()
			type = step['type']

			if type == 'solve':
				ret = self.make_queue()
				if ret == 'fail':
					return ret
				break
			
			if type == 'comment':
				break
			
			if type == 'set_moves':
				self.allowed_sequences = []
				for seq in step['sequence'].split(','):
					tmp = seq.strip().split(" ")
					self.allowed_sequences.append(tmp)
		
			elif type == 'set_search_moves':
				self.search_moves = step['value']
		
			
			elif type == 'set_mode':
				self.mode = step['value']
			
			elif type == 'set_flip_algo':
				self.flip_algo = step['sequence']
			
			elif type == 'insert':
				self.insert = step['value'] == 'True'

			elif type == 'req':
				if step['operation'] == 'add':
					self.rules.append(step['rule'])
				elif step['operation'] == 'remove':
					self.rules = [x for x in self.rules if x['rule_id'] != step['rule_id']]

	def next_move(self):
		#if we have a prepared move in stock just feed that one
		if len(self.queued_moves) == 0 and self.test_cube():
			return None

		if len(self.queued_moves) == 0:
			success = self.make_queue()
			if success == 'fail':
				return "fail"

		if len(self.queued_moves) > 0:
			pop = self.queued_moves.popleft()
			return pop
		else:
			return None

	def parse_rule(self, rule):
		parts = rule.split(',')
		parts = map(lambda x: x.strip(), parts)
		
		if parts[0] == 'Inner':

			m = {
					'1x1' : Block.inner_1x1,
					'2x1' : Block.inner_2x1,
					'2x2' : Block.inner_2x2,
					'3x1' : Block.inner_3x1,
					'3x3' : Block.inner_3x3,
					'3x2' : Block.inner_3x2,
					'1x1_corner' : Block.inner_1x1_corner
					}

			size = m[parts[1]]
			return (parts[0], size, parts[2], Face_Lookup[parts[3]])

		elif parts[0] == 'Build_Edge':
			#outer edge / center edge:
			return (parts[0], piece[parts[1]], orientation[parts[2]], parts[3], parts[4].split('-'))
		
		elif parts[0] == 'Edge':
			return (parts[0], parts[1], parts[2].split('-'))

		elif parts[0] == 'Store_Edge':
			self.stored += 1
			return (parts[0])

		elif parts[0] == 'Parity':
			#check if we have a parity error:

			mid = edge_pieces['LF'][1]
						
			top = edge_pieces['LF'][0]

			if self.same_piece(mid, top, oriented=Orientation.non_oriented):
				parity_fix = "F r r B B U U l U U rp U U r U U F F r F F lp B B r r"
				for move in parity_fix.split(" "):
					self.queued_moves.append(move)

		elif parts[0] == 'Cross':
			#self.rules = [] #must be reduced to a 3x3, so we can clear the old rules, might be stupid so ill remove the optimization for now
			self.cross += 1

		elif parts[0] == 'Corner':
			return (parts[0], parts[1], parts[2].split('-'), parts[3])
		elif parts[0] == 'F2L_Edge':
			return (parts[0], parts[1], parts[2].split('-'), parts[3])
		elif parts[0] in  ['OLL_Cross', 'OLL', 'PLL_Corners', 'PLL']:
			return (parts[0], parts[1])
		elif parts[0] == 'Pair':
			self.pairs += 1


	def load_state(self, s):

		prob = s.get_first_problem()

		self.cube.rotate(prob['all_commands'])
		self.rules = prob['rules']
		self.flip_algo = prob['flip_algo']
		self.mode = prob['mode']
		self.stored = prob['stored']
		
		f = open('search.algo', 'r')
		self.allowed_sequences = f.readlines()[0][:-1].split(",")

	def rev_seq(self, s):
		s.reverse()
		for i, m in enumerate(s):
			if(s[i][-1:] == 'p'):
				s[i] = m[:-1]
			else:
				s[i] = m + 'p'

	def make_queue(self):
		#print self.rules
		mods = self.allowed_sequences
		c = self.cube
		flip_algo = self.flip_algo #'R U Rp Up Fp U F'
		#print 'current rules', self.rules
		#print 'test cube:', self.test_cube()
		if self.test_cube():
			return
		t0 = time.time()
		search_time = 0
		while True:
			que = deque()
			done = False
			for m in mods:
				que.append(m)
			cnt = 0
			pre_turn_sticker_pos = []
			while len(que) > 0:
				cnt = cnt + 1
				self.search_cnt += 1
				s = que.popleft()
				if self.mode == 'inner':
					pre_turn_sticker_pos[:] = []
					pre_turn_sticker_pos = c.get_inner_sticker_positions(Face_Lookup[self.search_moves], self.insert)
				if cnt % 1000 == 0:
					#print "performed", cnt, "seach steps"
					pass
				if self.mode == 'build_edge':
					rev = []
					rev.extend(s)
					self.rev_seq(rev)

					s.extend(flip_algo.split(' '))
					s.extend(rev)
					#print "evaluating: ", s
				if time.time() - t0 > 10:
					print "                      ___                              "
					print "                   .-'   `'.                           "
					print "                  /         \                          "
					print "                  |         ;                          "
					print "                  |         |           ___.--,        "
					print "         _.._     |0) ~ (0) |    _.---'`__.-( (_.      "
					print "  __.--'`_.. '.__.\    '--. \_.-' ,.--'`     `\"\"`      "
					print " ( ,.--'`   ',__ /./;   ;, '.__.'`    __               "
					print " _`) )  .---.__.' / |   |\   \__..--\"\"  \"\"\"--.,_       "
					print "`---' .'.''-._.-'`_./  /\ '.  \ _.-~~~````~~~-._`-.__.'"
					print "      | |  .' _.-' |  |  \  \  '.               `~---` "
					print "       \ \/ .'     \  \   '. '-._)                     "
					print "        \/ /        \  \    `=.__`~-.                  "
					print "        / /\         `) )    / / `"".`\                "
					print "  , _.-'.'\ \        / /    ( (     / /                "
					print "   `--~`   ) )    .-'.'      '.'.  | (                 "
					print "          (/`    ( (`          ) )  '-;                "
					print "           `      '-;         (-'                      "
					
					print 'FAIL:', time.time() - t0
					print 'stepcnt', cnt
					print "FAIL, moves:", mods
					print "Fail rules:"
					for rule in self.rules:
						print rule['color'], ":", rule
					self.queued_moves.append('fail')
					return 'fail'
				c.rotate(s)
				if self.test_cube(): 
					if time.time() - t0 > 1:
						pass	
						#print "Hard step", self.rules
					done = True
			
				change_occurred = True

				if self.mode == 'inner': #optimization for building the 3x3, never move anything that doesnt move the interesting color
					post_turn_sticker_pos = c.get_inner_sticker_positions(Face_Lookup[self.search_moves], self.insert)
					post_turn_sticker_pos.sort()
					pre_turn_sticker_pos.sort()
					change_occurred = False
					if len(post_turn_sticker_pos) != len(pre_turn_sticker_pos):
						change_occurred
					else:
						for i in range(0, len(post_turn_sticker_pos)):
							if post_turn_sticker_pos[i] != pre_turn_sticker_pos[i]:
								change_occurred = True


				tp = time.time()

				#undo what we did to the mutable cube, then revert tho sequence to the correct one
				self.rev_seq(s)
				c.rotate(s)
				self.rev_seq(s)

				if done == True :
					for c in s:
						self.queued_moves.append(c)
					return

				#continue the bfs
				
				if not change_occurred:
					continue

				for m in mods:
					tmp = []
					tmp.extend(s)
					tmp.extend(m)
					que.append( tmp )


			print "No more moves found, choosing from", mods
			return 'fail'
	
	#handles inner faces, not for edges or corners
	def get_faces_with_inner_color(self, color):
		ret = []
		for face_id, face in enumerate(self.cube.state):
			for sticker in [6,7,8,11,13,16,17,18]: 
				if face[sticker] == Face_Lookup[color]:
					ret.append(Turns[face_id])
		return ret
	
	def same_piece(self, fst, snd, oriented=Orientation.non_oriented):
		fstleft = self.cube.state[fst.left_face()][fst.left_sticker()]
		fstright = self.cube.state[fst.right_face()][fst.right_sticker()]
		
		sndleft = self.cube.state[snd.left_face()][snd.left_sticker()]
		sndright = self.cube.state[snd.right_face()][snd.right_sticker()]

		if not oriented == Orientation.non_oriented and fstleft == sndleft and fstright == sndright:
			return True
		if not oriented == Orientation.oriented and fstleft == sndright and fstright == sndleft:
			return True
		return False

	#verifies if the cube satisfies all rules in its current state
	def test_cube(self, p=False):
		for color in Turns:
			ok = self.test_color(color, p)
			if not ok:
				return False
		#edge building rules:
		for rule in self.rules:
			c = self.cube
			if rule['step_type'] == 'Build_Edge':
				if rule[1] == Edge.outer:
					#and r[2] == Orientation.oriented:
					fr_mid = edge_pieces[rule[3]][1]
					
					#check all pairs in mid layer, except for FR
					found = False

					for edge_pos in rule[4]:
						for piece_id in [0,2]: #only want to look at top and bottom edges
							if self.same_piece(fr_mid, edge_pieces[edge_pos][piece_id], rule[2]):
								found = True
								break

					if not found:
						return False

			if rule['step_type'] == 'Edge':
				if rule[1] in ['2x1x1', '3x1x1']:
					for cur_place in rule[2]:

						fr_mid = edge_pieces[cur_place][1]
						
						top = edge_pieces[cur_place][0]
						
						bot = edge_pieces[cur_place][2]
						cnt = 0	

						if self.same_piece(fr_mid, top, oriented=Orientation.oriented):
							cnt += 1
						if self.same_piece(fr_mid, bot, oriented=Orientation.oriented):
							cnt += 1
						#print "cnt is", cnt, "on place", cur_place
						if rule[1] == '2x1x1' and cnt == 0:
							return False
						if rule[1] == '3x1x1' and cnt <= 1:
							return False
			if rule['step_type'] == 'Corner':
				cur_pos = self.cube.get_corner_position(rule[1])
				if cur_pos not in rule[2]:
					return False

				if rule[3] != 'Any':

					stickers = self.cube.get_corner_stickers(cur_pos)
					required_pos = rule[3]
					idx = cur_pos.find(required_pos)
					idx_face = stickers[idx]

					if idx_face != Face_Lookup[rule[1][0]]:
						return False
			if rule['step_type'] == 'F2L_Edge':
				cur_pos = self.cube.get_f2l_edge_position(rule[1])
				if cur_pos not in rule[2]:
					return False

				if rule[3] != 'Any':

					stickers = self.cube.get_edge_stickers(cur_pos)
					required_pos = rule[3]
					idx = cur_pos.find(required_pos)
					idx_face = stickers[idx]

					if idx_face != Face_Lookup[rule[1][0]]:
						return False
			if rule['step_type'] == 'OLL_Cross':
				print "Testing oll cross"
				for pos in range(1, 24):
					if pos == 4 or pos == 20:
						continue
					if self.cube.state[Face.U][pos] != Face.U:
						return False
			if rule['step_type'] == 'OLL':
				for pos in range(0, 25):
					if self.cube.state[Face.U][pos] != Face.U:
						return False
			corner_faces = [(Face.F, 0),(Face.F,4),(Face.L,4),(Face.L,24),(Face.B,20),(Face.B,24),(Face.R,0),(Face.R,20)]
			if rule['step_type'] == 'PLL_Corners':
				state = self.cube.state
				for i in corner_faces:
					if state[i[0]][i[1]] != i[0]:
						return False

			if rule['step_type'] == 'PLL':
				state = self.cube.state
				mid_pieces = [(Face.F, 2), (Face.L, 14), (Face.B, 22), (Face.R, 10)]
				corner_faces.extend(mid_pieces)
				for i in corner_faces:
					if state[i[0]][i[1]] != i[0]:
						return False

		found_stored = 0

		for cur_place in ['UF', 'UL',  'UB',  'UR',  'DF',  'DL',  'DB',  'DR'] :
			fr_mid = edge_pieces[cur_place][1]
			
			top = edge_pieces[cur_place][0]
			
			bot = edge_pieces[cur_place][2]
			cnt = 0	

			if self.same_piece(fr_mid, top, oriented=True):
				cnt += 1
			if self.same_piece(fr_mid, bot, oriented=True):
				cnt += 1
			if cnt >= 2:
				found_stored += 1
				if found_stored >= self.stored:
					break
		if found_stored < self.stored:
			return False
		
		found_cross = 0
		for cross_piece in ['DF', 'DL',  'DB',  'DR']:
			mid = edge_pieces[cross_piece][1]
			down_color = self.cube.state[mid.left_face()][mid.left_sticker()]
			up_color = self.cube.state[mid.right_face()][mid.right_sticker()]
			if down_color == Face.D and up_color == mid.right_face():
				found_cross += 1
		
		if found_cross < self.cross:
			return False
		done_pairs = 0
		for pair in ['FR','LF','BL','RB']:
			mid = edge_pieces[cross_piece][1]
			down_color = self.cube.state[mid.left_face()][mid.left_sticker()]
			up_color = self.cube.state[mid.right_face()][mid.right_sticker()]

			corner = self.cube.get_corner_stickers('D' + pair)
			if corner [0] == Face.D and corner[1] == down_color and corner[2] == up_color:
				done_pairs += 1
			pass
		if done_pairs < self.pairs:
			return False
		for corner in ['ULF', 'UBL', 'URB', 'UFR']:
			cor = self.cube.get_corner_stickers(corner)


		return True
		#for each face, examine what patterns they have in each color
		#TODO: handle pattern recognizion for each color

	#handles tests of the inner 3x3
	def test_color(self, color, p):
		num_blocks = []
		for i in range(0,7):
			num_blocks.append([0,0,0,0,0,0,0])
		for face in range (0,6):
			f = self.cube.state[face]
			used = []

			stickers = self.get_stickers(f, color )
			stickers = filter(lambda x: x in self.inner_3x3[0], stickers)

			#examine what we have on each side, one hit is enough since we never need 2 free 2x1 or 3x1 blocks in an incorrect position
			#3x3 and 3x2, only on d-face
			self.check_case(self.inner_3x3, Block.inner_3x3, num_blocks, face, used, stickers)
			self.check_case(self.inner_3x2, Block.inner_3x2, num_blocks, face, used, stickers)
			#3x1
			self.check_case(self.inner_3x1, Block.inner_3x1, num_blocks, face, used, stickers)

			#2x2 only D
			self.check_case(self.inner_2x2, Block.inner_2x2, num_blocks, face, used, stickers)

			#2x1
			self.check_case(self.inner_2x1, Block.inner_2x1, num_blocks, face, used, stickers)
			if p:
				print "Face is ", face, ", Used stuff: ", used
			#1x1 - only interesting on correct side
			self.check_case(self.inner_1x1, Block.inner_1x1, num_blocks, face, used, stickers)
			self.check_case(self.inner_1x1_corner, Block.inner_1x1_corner, num_blocks, face, used, stickers)

		if p:
			print "Color: ", color, ", num_blocks: ", num_blocks
		for r in self.rules:

			if r['step_type'] == 'inner':
				req_face = Face_Lookup[r['target_color']]
					
				if r['color'] != color:
					continue
				block_type = Rule_Lookup_Reversed[r['block']]
				needs_face = Face_Lookup[r['target_color']]
				if str(r['target_color']) != "Any":
					if( num_blocks[block_type][needs_face] > 0):
						if block_type in [Block.inner_3x2, Block.inner_2x2]: #for 3x2 we cannot have the same color on one of the other 3 spots
							cnt = 0
							for sticker in [6,7,8,11,13,16,17,18]:
								if self.cube.state[needs_face][sticker] == Face_Lookup[color]:
									cnt += 1
							if block_type == Block.inner_3x2 and cnt != 5:
								return False
							if block_type == Block.inner_2x2 and cnt > 4:
								return False

						num_blocks[block_type][needs_face] -= 1
					else:
						return False
				else:
					success = False
					for face in range(0,6):
						if face == req_face: #any means not on the solved side
							continue
						if num_blocks[block_type][face] > 0:
							num_blocks[block_type][face] -= 1
							success = True
							break
					if not success:
						return False

		return True

	#check if we have a case right now on the cube
	#cands is series of sticker-numbers that all needs to be correct color to have a correct value
	def check_case(self, cands, case, num_blocks, face, used, stickers):
		for cand in cands:
			success = True
			for a in cand:
				found = False
				for b in stickers:
					if a == b:
						found = True
						break;
				if not found:
					success = False
					break

				for b in used:
					if a == b:
						success = False
						break
			if success:
				num_blocks[case][face] += 1
				if case == self.inner_3x1:
					num_blocks[self.inner_2x1][face] += 1
					num_blocks[self.inner_1x1][face] += 1
				used.extend(cand)
				return

	def get_stickers(self, face, color):
		ret = []

		for id, sticker in enumerate(face):
			if sticker == Face_Lookup[color]:
				ret.append(id)

		return ret

