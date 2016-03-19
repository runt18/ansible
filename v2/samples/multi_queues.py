#!/usr/bin/env python

import sys
import time
import Queue
import traceback
import multiprocessing

from ansible.inventory import Inventory
from ansible.inventory.host import Host
from ansible.playbook.play import Play
from ansible.playbook.task import Task
from ansible.executor.connection_info import ConnectionInformation
from ansible.executor.task_executor import TaskExecutor
from ansible.executor.task_result import TaskResult
from ansible.parsing import DataLoader
from ansible.vars import VariableManager

from ansible.utils.debug import debug

NUM_WORKERS = 20
NUM_HOSTS   = 1778
NUM_TASKS   = 1

def results(final_q, workers):
   cur_worker = 0
   def _read_worker_result(cur_worker):
      result = None
      starting_point = cur_worker
      while True:
         (worker_prc, main_q, res_q) = workers[cur_worker]
         cur_worker += 1
         if cur_worker >= len(workers):
            cur_worker = 0

         try:
            if not res_q.empty():
               debug("worker {0:d} has data to read".format(cur_worker))
               result = res_q.get()
               debug("got a result from worker {0:d}: {1!s}".format(cur_worker, result))
               break
         except:
            pass

         if cur_worker == starting_point:
            break

      return (result, cur_worker)

   while True:
      result = None
      try:
         (result, cur_worker) = _read_worker_result(cur_worker)
         if result is None:
            time.sleep(0.01)
            continue
         final_q.put(result, block=False)
      except (IOError, EOFError, KeyboardInterrupt) as e:
         debug("got a breaking error: {0!s}".format(e))
         break
      except Exception as e:
         debug("EXCEPTION DURING RESULTS PROCESSING: {0!s}".format(e))
         traceback.print_exc()
         break

def worker(main_q, res_q, loader):
   while True:
      task = None
      try:
         if not main_q.empty():
            (host, task, task_vars, conn_info) = main_q.get(block=False)
            executor_result = TaskExecutor(host, task, task_vars, conn_info, loader).run()
            debug("executor result: {0!s}".format(executor_result))
            task_result = TaskResult(host, task, executor_result)
            res_q.put(task_result)
         else:
            time.sleep(0.01)
      except Queue.Empty:
         pass
      except (IOError, EOFError, KeyboardInterrupt) as e:
         debug("got a breaking error: {0!s}".format(e))
         break
      except Exception as e:
         debug("EXCEPTION DURING WORKER PROCESSING: {0!s}".format(e))
         traceback.print_exc()
         break

loader = DataLoader()

workers = []
for i in range(NUM_WORKERS):
   main_q = multiprocessing.Queue()
   res_q  = multiprocessing.Queue()
   worker_p = multiprocessing.Process(target=worker, args=(main_q, res_q, loader))
   worker_p.start()
   workers.append((worker_p, main_q, res_q))

res_q = multiprocessing.Queue()
res_p = multiprocessing.Process(target=results, args=(res_q, workers))
res_p.start()

def send_data(obj):
   global cur_worker
   global workers
   global pending_results

   (w_proc, main_q, wrkr_q) = workers[cur_worker]
   cur_worker += 1
   if cur_worker >= len(workers):
      cur_worker = 0

   pending_results += 1
   main_q.put(obj, block=False)
 
def _process_pending_results():
   global res_q
   global pending_results
   
   while not res_q.empty():
      try:
         result = res_q.get(block=False)
         debug("got final result: {0!s}".format(result))
         pending_results -= 1
      except Queue.Empty:
         pass

def _wait_on_pending_results():
   global pending_results
   while pending_results > 0:
      debug("waiting for pending results ({0:d} left)".format(pending_results))
      _process_pending_results()
      time.sleep(0.01)


debug("starting")
cur_worker      = 0
pending_results = 0


var_manager = VariableManager()

debug("loading inventory")
inventory = Inventory(host_list='/tmp/med_inventory', loader=loader, variable_manager=var_manager)
hosts = inventory.get_hosts()[:]
debug("done loading inventory")

ci = ConnectionInformation()
ci.connection = 'local'

for i in range(NUM_TASKS):
   #for j in range(NUM_HOSTS):
   for h in hosts:
      debug("queuing {0!s} {1:d}".format(h, i))
      #h = Host(name="host%06d" % j)
      t = Task().load(dict(name="task {0:d}".format(i), debug="msg='hello from {0!s}, {1:d}'".format(h, i)))
      #t = Task().load(dict(name="task %d" % (i,), ping=""))
      #task_vars = var_manager.get_vars(loader=loader, host=h, task=t)
      task_vars = dict()
      new_t = t.copy()
      new_t.post_validate(task_vars)
      send_data((h, t, task_vars, ci))
      debug("done queuing {0!s} {1:d}".format(h, i))
      _process_pending_results()
   debug("waiting for the results to drain...")
   _wait_on_pending_results()

res_q.close()
res_p.terminate()

for (w_p, main_q, wrkr_q) in workers:
   main_q.close()
   wrkr_q.close()
   w_p.terminate()

debug("done")
