# %%
import time
from threading import Thread, Lock
from math import inf

# %%
def compare(word, solution):
    response = 0
    for w in range(len(word)):
        response = response * 10
        if word[w] == solution[w]:
            response = response + 2
        elif word[w] in solution:
            response = response + 1
    return response

def get_sets(word, remaining):
    combs = {}
    for solution in remaining:
        score = compare(word, solution)
        combs.setdefault(score, [])
        combs.setdefault(score, []).append(solution)
    return combs

def filter_set(remaining, word, response):
    return [r for r in remaining if compare(word, r) == response]

# %%
# Each node need to know: remaining feasible set
# Optionally: parent, and current move counter
class Node:
    def __init__(self, parent, remaining, counter, info):
        self.parent = parent
        self.children = {}
        self.child_scores = {}
        self.remaining = remaining
        self.counter = counter
        self.expanded = False
        self.finished = False
        self.pruned = False
        self.avg_moves = None
        self.best_move = ''
        self.local_bound = inf
        self.info = info
        self.pruned_children = []
        self.lock = Lock()
        # print(f"New Node: {parent} {counter} {info} {remaining}")

    def get_status(self):
        return {
            'id': id(self),
            'parent': self.parent,
            'remaining': self.remaining,
            'counter': self.counter,
            'expanded': self.expanded,
            'finished': self.finished,
            'pruned': self.pruned,
            'avg_moves': self.avg_moves,
            'children': len(self.children),
            'best_move': self.best_move,
            'info': self.info
        }

    def check(self, global_bound):
        if self.pruned:
            return
        with self.lock:
            score = {}
            completed = True
            if len(self.children) > 0:
                set_size = len(self.remaining)
                for word, word_children in self.children.items():
                    if word in self.pruned_children:
                        continue
                    if self.child_scores.get(word) is not None:
                        continue
                    word_done = True
                    # print(word, word_children)
                    for response, response_child in word_children.items():
                        if not response_child.finished:
                            word_done = False
                            completed = False
                            continue

                        if response_child.finished and response_child.avg_moves is None:
                            word_done = False
                            self.pruned_children.append(word)
                            break
                        else:
                            child_score = len(response_child.remaining) / set_size * response_child.avg_moves
                            score[word] = score.get(word, 0) + child_score
                    if word_done:
                        # print(f"New value added: {self.info} {word} {score[word]}")
                        self.child_scores[word] = score[word]
                        self.local_bound = min(self.local_bound, score[word])
                        # print(f"LOCAL BOUND UPDATED: {self.info} by {word}: {self.local_bound}")

            score = self.child_scores
            for word in score:
                if word in self.pruned_children:
                    continue # already pruned
                if score[word] > global_bound or score[word] > self.local_bound: # already worse than best case
                    # print(f"PRUNING CHILD NODE: {self.info} for word {word} score {score[word]} bound {self.local_bound} and {global_bound}")
                    for response_child in self.children[word].values():
                        response_child.prune()
                    self.pruned_children.append(word)

        # if len(self.children) == 0 and self.counter > 1:
        #     self.prune()
        #     if self.parent:
        #         self.parent.check(global_bound)
        # else:
        #     self.finished = True
        #     return

        if completed:
            self.finished = True
            if len(score) == 0:
                self.prune()
                if self.parent:
                    self.parent.check(global_bound)
                return
            best_word = min(score, key=score.get)
            self.avg_moves = score[best_word]
            self.best_move = best_word
            # if self.counter <= 2:
                # print("COMPLETED")
                # print(self.get_status())
                # print(score)
            if self.parent:
                self.parent.check(min(self.local_bound, global_bound))

    def prune(self):        
        if self.pruned:
            return
        with self.lock:
            # print(f"PRUNED {self.info}")
            self.pruned = True
            self.finished = True
            for word, word_children in self.children.items():
                for response, response_child in word_children.items():
                    if not response_child.finished:
                        response_child.prune()

    def set_solved(self):
        self.finished = True
        self.avg_moves = self.parent.counter

# %%
# Each worker picks up next available job possible and expands the set
class Worker:
    def __init__(self, id, controller):
        self.id = id
        self.controller = controller
    
    def __call__(self):
        print(f"Start worker {self.id}")
        while self.controller.has_more():
            self.run()
        print(f"End worker: {self.id}")

    def run(self):
        node = self.controller.get_next()
        if node is None:
            time.sleep(0.1)
            return

        if node.counter > 6:
            node.finished = True
            node.avg_moves = 7
            node.parent.check(self.controller.get_bound())
            return
            # node.prune()
            # node.parent.check(self.controller.get_bound())
            return

        if node.pruned:
            # node.finished = True
            # node.avg_moves = None
            # node.parent.check(self.controller.get_bound())
            return

        if len(node.remaining) == 1:
            node.finished = True
            node.avg_moves = node.counter
            node.best_move = node.remaining[0]
            # print(node.get_status())
            parent = node.parent
            if parent:
                parent.check(self.controller.get_bound())
            return

        search_space = self.controller.get_search_space(node)
        for word, sets in search_space:
            if word in node.info:
                continue
            # sets = get_sets(word, node.remaining)
            children_dict = node.children.setdefault(word, dict())
            # print(word, sets)
            for response in sets:
                child = Node(node, sets[response].copy(), node.counter + 1, node.info.copy() + [word, response])
                children_dict[response] = child
                if response == 22222:
                    child.set_solved()
                else:
                    self.controller.add_node(child)
            node.expanded = True


# %%
class Controller():

    def __init__(self, first_node):
        self.active_nodes = [first_node]
        self.first_node = first_node
        self.global_bound = inf
        self.node_lock = Lock()
        # self.workers = [Worker(1, self)]

    def start(self):
        if True:
            workers = [Worker(i, self) for i in range(15)]
            threads = [Thread(target=w) for w in workers]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
        else:
            w = Worker(1, self)
            w.__call__()

    def get_search_space(self, node):
        # selected_words = []
        all_sets = tuple(get_sets(word, node.remaining) for word in node.remaining)
        scoring = [max(len(j) for j in i.values()) for i in all_sets]
        topN = set(sorted(scoring)[0:5])
        pairs = tuple(zip(node.remaining, all_sets))
        return (pairs[i] for i in range(len(node.remaining)) if scoring[i] in topN)
        # for (index, word) in enumerate(node.remaining):
        #     if scoring[index] in topN:
        #         selected_words.append((word, all_sets[index]))
        # return tuple(selected_words)
        return zip(node.remaining, [get_sets(w, node.remaining) for w in node.remaining])
        # return solution_set[0:20]

    def add_node(self, node):
        with self.node_lock:
            self.active_nodes.append(node)

    def get_next(self, method='smallest_set'):
        with self.node_lock:
            self.active_nodes = [i for i in self.active_nodes if not i.pruned and not i.finished]
        if len(self.active_nodes) > 0:
            # ordered
            if method == 'ordered':
                with self.node_lock:
                    node = self.active_nodes.pop(0)
            elif method == 'smallest_set':
                with self.node_lock:
                    set_sizes = [[-i.counter, len(i.remaining)] for i in self.active_nodes]
                    min_index = set_sizes.index(min(set_sizes))
                    node = self.active_nodes.pop(min_index)
            # print(f"Processing {id(node)}")
            return node
        else:
            return None

    def get_bound(self):
        return self.global_bound

    def update_bound(self, value):
        self.global_bound = min(self.global_bound, value)

    def has_more(self):
        with self.node_lock:
            print(f"Remaining nodes: {len(self.active_nodes)}")
            return len(self.active_nodes) > 0 or not self.first_node.finished


# %%
with open("solutions.txt") as f:
    text = f.read()
    solution_set = [i.replace('"', '').replace(' ', '') for i in text.split(",")]
solution_set[0:5]

# %%
with open("nonsolutions.txt") as f:
    text = f.read()
    nonsolution_set = [i.replace('"', '').replace(' ', '') for i in text.split(",")]
nonsolution_set[0:5]


from multiprocessing import freeze_support
if __name__ == "__main__":

    freeze_support()

    # %%
    target = solution_set

    initial_node = Node(None, target, 1, ['StartNode'])
    c = Controller(initial_node)
    t0 = time.time()
    c.start()
    t1 = time.time()
    initial_node.get_status()


    # %%
    print(initial_node.get_status())

    print(t1-t0, "seconds")

    print(initial_node.child_scores)


# OUTPUT:
# {'id': 2810956786416, 'parent': None, 'remaining': [...],
# 'counter': 1, 'expanded': True, 'finished': True, 'pruned': False, 
# 'avg_moves': 3.6064794816414625, 
# 'children': 5,
# 'best_move': 'raise',
# 'info': ['StartNode']}
# 126.79092383384705 seconds
# {'arise': 3.6172786177105793, 'raise': 3.6064794816414625, 'alone': 3.6138228941684627, 'arose': 3.620302375809929, 'atone': 3.625485961123108}