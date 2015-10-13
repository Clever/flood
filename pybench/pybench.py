#! /usr/bin/env python
"""
Script to benchmark http servers
"""

import argparse
import matplotlib
# disable matplotlib GUI
matplotlib.use('Agg')
from matplotlib import pyplot
import os
import time
from twisted.internet import (defer,
							  reactor)
from twisted.web.client import Agent
from twisted.web.http_headers import Headers
from urlparse import urlparse


def parseURL(url):
	"""
	Parse the domain from the url
	@param url: request url
	@return: domain name
	"""
	u = urlparse(url)
	return u.netloc or u.scheme

class Result(object):
	"""
	Object for storing request results
	"""
	def __init__(self):
		self.Started = 0
		self.Finished = 0
		self.Elapsed = 0
		self.Code = 0
		self.Timeout = False

	def start(self):
		"""Call when the request is made"""
		self.Started = time.time()

	def done(self, code, timed_out=False):
		"""
		Call when the request is complete
		@param code: response code
		@param timed_out: (optional) mark the request as having timed out
		"""
		self.Finished = time.time()
		self.Elapsed = self.Finished - self.Started
		self.Code = code
		self.Timeout = timed_out

	def __str__(self):
		return "Time: %.2f, Elapsed: %dms, Code: %s"%(self.Started, self.Elapsed*1000, self.Code)


class Bench(object):
	"""
	Class for benchmarking http servers
	"""
	def __init__(self, requests, concurrency, url, timelimit=None, auth=""):
		"""
		@param requests: number of requests to send
		@param concurrency: number of requests to send in parallel
		@param url: will send GET requests to this url
		@param timelimit: (optional) time limit for the test (will override requests if not done yet)
		@param auth: (optional) Authorization string to send
		"""
		self.Requests = requests
		self.Concurrency = concurrency
		self.Timelimit = timelimit
		self.Headers = Headers({'Authorization':[auth]})
		self.Url = url

		self.Agents = [Agent(reactor) for x in range(concurrency)]
		self.Results = []

		self.ActiveQueries = {}
		self.QueriesMade = 0
		self.StopCall = None
		self.RunDeferred = None
		self.Stopped = False

	def _makeRequests(self, agents):
		"""
		make requests for the url
		@param agents: list of agents available to make requests
		"""
		if self.Stopped:
			return

		for agent in agents:
			# setup result holder
			result = Result()
			self.Results.append(result)
			result.start()

			# make the request
			dfr = agent.request('GET', self.Url, self.Headers, None)
			self.ActiveQueries[agent] = dfr
			dfr.addCallback(self._callback, result, agent)
			dfr.addErrback(self._errback, result, agent)
			
			self.QueriesMade += 1
			if self.QueriesMade >= self.Requests:
				self.stop()

	def _callback(self, response, result, agent):
		"""
		Called when a request receives a response
		@param response: Response object
		@param result: L{Result} object for the request
		@param agent: agent that made the request
		"""
		result.done(response.code)
		self._makeRequests([agent])

	def _errback(self, error, result, agent):
		"""
		Called when a request fails.
		@param error: Failure object
		@param result: The L{Result} object for the request
		@param agent: agent that made the request
		"""
		result.done(error)
		self._makeRequests([agent])

	def _done(self, ignore):
		"""
		called when the test has completed and cleaned up.
		"""
		self.RunDeferred.callback(self.Results)

	def stop(self):
		self.Stopped = True
		print "Sent %s requests. Cleaning up..."%(self.QueriesMade)
		# Wait for the active queries to complete
		dfr = defer.DeferredList(self.ActiveQueries.values())
		dfr.addBoth(self._done)

		# disable the stop timer
		if self.StopCall is not None:
			if self.StopCall.active():
				self.StopCall.cancel()
		
	def run(self):
		"""
		Run the test.
		@return: deferred list of L{Result} objects
		"""
		print "Benchmarking %s"%(parseURL(self.Url))
		self.RunDeferred = defer.Deferred()
		
		if self.Timelimit:
			self.Requests = 5000
			self.StopCall = reactor.callLater(self.Timelimit, self.stop)

		# start the requests.
		self._makeRequests(self.Agents)
		return self.RunDeferred


def summary(results, graph_file, domain, concurrency):
	"""
	callback for the test results. Generate the graph and prints
	the summary.
	@param results: list of L{Result} objects
	@param graph_file: path to write the graph file to
	@param domain: domain name of the url tested
	@param concurrency: number of concurrent requests
	"""

	start_time = min([r.Started for r in results])
	longest = max([r.Elapsed for r in results])
	avg_time = sum([r.Elapsed for r in results])/len(results)

	# generate graph
	if graph_file:
		success_x = []
		success_y = []

		errors_x = []
		errors_y = []
		for result in results:
			if result.Code == 200:
				success_x.append(result.Started - start_time)
				success_y.append(result.Elapsed*1000)
			else:
				errors_x.append(result.Started - start_time)
				errors_y.append(result.Elapsed*1000)

		success_plt = pyplot.scatter(success_x,
		  			  		         success_y,
								     c=[0.5, 0.5, 0.5],
								     marker='o',
								     edgecolor='',
								     label="successes")
		error_plt = pyplot.scatter(errors_x,
							       errors_y,
							       c='r',
							       marker='^',
							       edgecolor='',
							       label="errors")
		if longest - avg_time > avg_time*4:
			pyplot.yscale('log')
		pyplot.grid(b=True,
				    which='major',
				    color=[0.8, 0.8, 0.8],
				    linestyle='--')
		pyplot.legend([success_plt,error_plt],
					  ["successes", "errors"])

		pyplot.xlabel("Time of Request (seconds)")
		pyplot.ylabel("Response Time (ms)")
		test_name = os.path.splitext(graph_file)[0]
		pyplot.title("PyBench: %s\n%s n=%d, c=%d"%(domain,
												   test_name,
												   len(results),
												   concurrency))
		pyplot.savefig(graph_file, bbox_inches='tight')

	# calculate summary page
	stop_time = max([r.Finished for r in results])
	elapsed_time = stop_time - start_time
	per_sec = len(results)/(elapsed_time)
	errors = 0
	for result in results:
		if result.Code != 200:
			errors += 1

	print "-"*30
	print "Total Time: %.2fs"%(elapsed_time)
	print "Average Request Length: %dms"%(avg_time*1000)
	print "Longest Request: %dms"%(longest*1000)
	print "Average Requests per second: %d"%(per_sec)
	print "Total Errors: %d"%(errors)
	print "-"*30
	reactor.stop()


def run_test(requests, concurrency, url, timelimit=None, auth=None, graph_file=None):
	"""
	Run the benchmarking test and print the results
	@param requests: number of requests to send
	@param concurrency: number of requests to send in parallel
	@param url: will send GET requests to this url
	@param timelimit: (optional) time limit for the test (will override requests if not done yet)
	@param auth: (optional) Authorization string to send
	@param graph_file: (optional) png file to create
	"""
	bench = Bench(requests, concurrency, url, timelimit=timelimit, auth=auth)
	dfr = bench.run()
	dfr.addBoth(summary, graph_file, parseURL(url), concurrency)


def main():
	parser = argparse.ArgumentParser()
	parser.add_argument('-n', type=int, default=100, help="Number of requests to perform")
	parser.add_argument('-c', type=int, default=10, help="Number of multiple requests to make at a time")
	parser.add_argument('-t', type=int, help="Seconds to max. to spend on benchmarking (implies -n 5000)")
	parser.add_argument('-A', type=str, help="Authentication header")
	parser.add_argument('-g', type=str, help="Graph the results and write them to the given filename (PNG)")
	parser.add_argument('url', help="Url to query")
	args = parser.parse_args()

	if not args.url.startswith("http://"):
		args.url = "http://" + args.url

	reactor.callWhenRunning(run_test, args.n, args.c, args.url, args.t, args.A, args.g)
	reactor.run()


if __name__ == "__main__":
	main()