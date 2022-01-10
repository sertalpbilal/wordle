
# %%
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from itertools import repeat
import time
from functools import lru_cache
from multiprocessing import freeze_support
import pprint
import json
from math import log

# %%
@lru_cache()
def get_response(guess, solution):
    response = ""
    for w in range(len(guess)):
        # response = response * 10
        if guess[w] == solution[w]:
            response += "2"
        elif guess[w] in solution:
            response += "1"
        else:
            response += "0"
    return response

# %%
def get_possible_outcomes(guess, remaining):
    responses = [[solution, get_response(guess, solution)] for solution in remaining]
    outcomes = list(set(r[1] for r in responses))
    outcome_dict = {o: 0 for o in outcomes}
    for r in responses:
        outcome_dict[r[1]] += 1
    outcomes_with_length = list(outcome_dict.items())
    return outcomes_with_length

def get_score(guess, remaining, target='min_max_set'):
    outcomes = get_possible_outcomes(guess, remaining)
    if target == 'min_max_set':
        max_set_size = max([v[1] for v in outcomes])
        return [guess, max_set_size]
    elif target == 'min_entropy':
        pmfs = [o[1]/len(remaining) for o in outcomes]
        return [guess, -sum([-i*log(i) for i in pmfs])]

def get_best(remaining):
    with ThreadPoolExecutor(max_workers=15) as executor:
        word_scores = list(executor.map(get_score, remaining, repeat(remaining))) #  [[word, get_score(word, remaining)] for word in remaining]
    scores = [entry[1] for entry in word_scores]
    min_score = min(scores)
    idx = scores.index(min_score)
    return word_scores[idx][0]

def filter_words(guess, remaining, response):
    feasible_words = [i for i in remaining if get_response(guess, i) == response]
    return feasible_words

def inside_processing(word_index, word, all_words, remaining, initial_filter, ctr, history, best_choice, array):
    if ctr == 1:
        print(f"{word_index}/{len(remaining)}: {word}")
    if initial_filter[word_index] == False:
        return 999 # Prune branch
    outcomes = get_possible_outcomes(word, remaining)
    total = sum(i[1] for i in outcomes) # count case sum
    values = []
    failed = False
    # if ctr > 8:
    #     return 9
    for o in outcomes:
        if o[1] == 0:
            continue
        if o[0] == '22222':
            values.append(ctr)
            continue
        subset = filter_words(word, remaining, o[0])
        all_word_subset = filter_words(word, all_words, o[0])
        history[o[0]] = {}
        best_choice[o[0]] = {}
        pass_array = array.copy()
        pass_array.append(o[0])
        best_word, val = recursive_best(all_word_subset, subset, ctr+1, history[o[0]], best_choice[o[0]], pass_array)
        
        if val is None:
            history[o[0]] = {'status': 'FAILED', 'code': 1099}
            failed = True
            values = [999] * len(outcomes)
            break
        values.append(val)
        best_choice[o[0]] = (best_word, val)
    # probability times number of avg moves
    score = sum([outcomes[idx][1]/total * values[idx] for idx in range(len(outcomes))])
    return score


def recursive_best(all_words, remaining, ctr=1, history=None, best_choice=None, array=None):

    debug = False

    if history is None:
        history = dict()
    
    if best_choice is None:
        best_choice = dict()

    if array is None:
        array = []

    if ctr > 8:
        return remaining[0], 9 # Fail mode

    all_words = remaining.copy()

    best_set_score = 0
    if True: # or len(remaining) > 10:
        if ctr == 1:
            print("Calculating initial scores")
        set_scores = []
        for word in all_words:
            set_score = get_score(word, tuple(remaining))
            set_scores.append(set_score[1])
        # best_set_score = min(set_scores)
        # initial_filter = [set_scores[i] <= best_set_score*1.1 for i in range(len(all_words))]
        # up to 50
        set_scores_top = set(sorted(set_scores)[0:10])
        initial_filter = [set_scores[i] in set_scores_top for i in range(len(all_words))]
    else:
        initial_filter = [True] * len(all_words)

    # if ctr >= 3:
    #     all_words = remaining.copy()

    if ctr == 1:
        print("Starting loop")
    word_scores = []
    if not debug:
        pass_array = []
        for word in all_words:
            pass_array.append(array.copy() + [word])
        if ctr <= 1:
            with ProcessPoolExecutor(max_workers=15) as executor: # word_index, word, remaining, debug, initial_filter, ctr
                word_scores = list(executor.map(inside_processing, list(range(len(all_words))), all_words, repeat(all_words), repeat(remaining), repeat(initial_filter), repeat(ctr), repeat(dict()), repeat(dict()), pass_array))
        elif ctr <= 2:
            with ThreadPoolExecutor(max_workers=15) as executor: # word_index, word, remaining, debug, initial_filter, ctr
                word_scores = list(executor.map(inside_processing, list(range(len(all_words))), all_words, repeat(all_words), repeat(remaining), repeat(initial_filter), repeat(ctr), repeat(dict()), repeat(dict()), pass_array))
        else:
            word_scores = [inside_processing(index, word, all_words, remaining, initial_filter, ctr, dict(), dict(), pass_array[index]) for (index, word) in enumerate(all_words)]
    else:
        for index, word in enumerate(all_words):
            history[word] = {}
            best_choice[word] = {}
            v = inside_processing(index, word, all_words, remaining, initial_filter, ctr, history[word], best_choice[word], [])
            word_scores.append(v)
    word_scores = [v if v is not None else 999999 for v in word_scores]
    best_word_score = min(word_scores)
    index = word_scores.index(best_word_score)
    if ctr == 1:
        return all_words[index], best_word_score, history, best_choice
    else:
        return all_words[index], best_word_score

if __name__ == '__main__':
    freeze_support()

    print("Reading solutions")
    with open("solutions.txt") as f:
        text = f.read()
        solution_set = [i.replace('"', '').replace(' ', '') for i in text.split(",")]

    print("Reading non-solutions")
    with open("nonsolutions.txt") as f:
        text = f.read()
        nonsolution_set = [i.replace('"', '').replace(' ', '') for i in text.split(",")]

    # all_words = solution_set + nonsolution_set
    all_words = solution_set

    print("Starting run")
    t0 = time.time()
    word, avg_trial, history, best_choice = recursive_best(all_words, solution_set, 1)
    print(word, avg_trial)
    t1 = time.time()
    print("Time", t1-t0)

    # with open('debug.json', 'w') as f:
    #     json.dump(history, f, indent=4)
