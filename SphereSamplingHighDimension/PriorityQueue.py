import sys, os
import itertools
from heapq import *

class PriorityQueue:
    def __init__(self):
        self.mPriQue = []                    	# list of entries arranged in a heap
        self.mEntryFinder = {}               	# mapping of tasks to entries
        self.mREMOVED = '<self.mREMOVED-task>'  # placeholder for a self.mREMOVED task
        self.mCounter = itertools.count()     	# unique sequence count
        
    def push(self, task, priority):
        'Add a new task or update the priority of an existing task'
        if task in self.mEntryFinder:
            self.remove_task(task)
        count = next(self.mCounter)
        entry = [priority, count, task]
        self.mEntryFinder[task] = entry
        heappush(self.mPriQue, entry)

    def find(self, task):
        if task in self.mEntryFinder:
            return self.mEntryFinder[task];
        else:
            return None;

    def remove_task(self, task):
        'Mark an existing task as self.mREMOVED.  Raise KeyError if not found.'
        entry = self.mEntryFinder.pop(task)
        entry[-1] = self.mREMOVED

    def pop(self):
        'Remove and return the lowest priority task. Raise KeyError if empty.'
        while self.mPriQue:
            priority, count, task= heappop(self.mPriQue)
            if task is not self.mREMOVED:
                entry = self.mEntryFinder[task];
                del self.mEntryFinder[task]
                return task, entry[0];  # task, F
        raise KeyError('pop from an empty priority queue')

    def isEmpty(self):
        return len(self.mPriQue) == 0;

    def count(self):
        return len(self.mPriQue);


#pq = PriorityQueue()

#pq.push(4,4);
#pq.push(4,5);
#pq.push(5,5);
#pq.push(3,3);
#pq.push(2,2);
#pq.push(6,6);
#pq.push(7,7);
#pq.push(9,9);

#pq.remove_task( 6 );
#task = pq.find( 4 );
#print task


#print pq.pop()
#print pq.count();
#print pq.pop()
#print pq.count();
#print pq.pop()
#print pq.count();
#print pq.pop()
#print pq.count();
#print pq.pop()
