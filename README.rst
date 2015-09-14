codetrawl
=========

This is a little idiosyncratic and undocumented tool for when you want
to get a list of everyone in the world who is using some API (e.g. so
you know who to talk to if you want to break it).

Well, not everyone in the world. But it knows how to search GitHub
(via screen scraping, because the `search API is useless for this,
woohoo
<https://developer.github.com/changes/2013-10-18-new-code-search-requirements/>`_), and `searchcode.com
<searchcode.com>`_ which covers basically all of bitbucket, Fedora,
and others.


Github notes
------------

GitHub code search `documentation
<https://help.github.com/articles/searching-code/>`_.

The query language is extremely quirky -- I don't understand the
tokenization rules at all, for example. Do quotes in the search string
do something? Maybe? Anyway, `try out your search manually first
<https://github.com/search?type=Code>`_.

IMPORTANT: you can never see beyond 1000 results for a single
search. If your search has more than this, then you need to figure out
how to break it into multiple sub-searches. E.g., you can search
separately by each language (using ``language:C``, ``language:C++``,
etc.), or if searching for ``a`` gives >1000 results, then try instead
taking the union of ``a AND b`` and ``a NOT b`` (each of which
hopefully have <=1000 results). Of course the trick is to figure out
what to use for ``b`` -- unfortunately neither I nor Github support
have ideas for how to do this robustly or automatically. (A seemingly
clever idea was to use the ``size:`` specified to slice the data into
files of size 0-1000 bytes, 1000-2000 bytes, etc., but in practice
such searches seem to time-out on the server side and return partial
results, so they're useless for this purpose.)

Here are some valid language codes: ``C``, ``C++`` *or* ``cpp``,
``objective-c``, ``python``, ``cython``. Swig apparently gets detected
as being "C" (`example
<https://github.com/search?l=c&q=PyArray_Dtype+in%3Afile%2Cpath+NOT+numpy%2Fcore+NOT+extras%2Fnumpy_include+NOT+ndarrayobject&ref=searchresults&type=Code&utf8=%E2%9C%93>`_).

Some challenges that codetrawl.py works hard to overcome:

* Sometimes a search that normally works will randomly have a
  server-side timeout. We only give up on a query if we see three
  server-side timeouts in a row.
* Github has throttling controls to prevent abuse, which appear to be
  signalled with a ``429 Too Many Requests`` HTTP error. If we see
  this then we retry with exponential backoff until we succeed.
* The order of search results is not stable, so if you have 5 pages of
  search results, just requesting each of these pages may or may not
  give you all of the results. A particular hit might appear on page 3
  while you're fetching page 2, and then on page 2 when you're
  fetching page 3, so you miss it. (And of course you can see the same
  hit twice this way as well.) So if github says there are 123
  results, we keep refreshing the search results until we see 123
  unique results.


Searchcode notes
----------------

Searchcode is less tricky -- you can basically just do a string
search, and get up to 4900 results. There's no throttling or
anything.

I haven't done any exhaustive checking on whether paging through the
results actually gives you all the results, but it did at least pass
some spot-checks that github search fails.

According to its author, it's believed to cover:

* Part of Github (~3 million repositories, which turns out to only be
  a fraction of Github -- though it's biased towards higher profile
  projects.)
* All of Bitbucket
* All of Fedora (though possibly out of date)
* All of CodePlex
* Substantial chunks of: Google Code, Sourceforge, Tizen, Android,
  Minix3, GNU, ...
