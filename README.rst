=======
htmlhub
=======

Serve html-templates from github in a controlled manner.

Introduction
============

The problem
-----------

We develop flat html-templates commonly as part of building a web application.
These html templates are used for everyone involved in the project to see what
a finished page ought to look like.

In addition the html within these is chopped up and used in the actual application templates.

Seeing the templates generally requires you to clone the github repository
locally, and then to point a web browser at them.  This is trivial for the
developers, but other stakeholders (particularly the customer) do not find this
so easy.

The solution
------------

htmlhub uses the github API to proxy the contents of the html-templates
directory directly from github into your browser.  By crafting the correct URL
you can serve these pages as if they were coming from a local checkout.

Security
--------

An htmlhub server will only serve files from within a directory called `html-templates` at the root of a repository.

It will only serve files from `html-templates` directories that contain a file
called `passwd`.

It also provides authentication.  The `passwd` file is parsed like an apache
**htpasswd** format file, requiring authentication before showing the
templates.

Using htmlhub
=============

Setting up github
-----------------

#. create a new user in your organisation's github account.
#. create a new team in your organisation and give it read-only access.
#. put the new user in the new team.
#. add the repositories you wish to view to the team.
#. log in as the new user and generate a "Personal access token" from the settings page.

Create the configuration file
-----------------------------

This should be placed in <sys.prefix>/etc/htmlhub.conf by default (sys.prefix
is the root of your python virtualenv) and look like::

    [github]
    username = <github user username>
    password = <personal access token>

    [cache]
    expiry = 30

The expiry is how long content is cached in memory in the htmlhub server.  If
data is never cached then pages will take longer to load, because every item is
fetched every single time from github, which can be slow for furniture
elements. 30 seconds seems to work well.

Now run your server.

Accessing templates
===================

To make a repository work with htmlhub:

#. make sure there is an html-templates directory with something in it
#. create a password file with some credentials in it (See below)
#. make sure the repository is in the team access list for your htmlhub user in github

Then you can navigate to a file in the html-templates directory on any branch by constructing a url like::

    http://server/<owner>/<repository>/<branch>/<path/to/file>

For example for:

 * organization: isotoma
 * repository: example
 * branch: master
 * filename: index.html

You would put::

    http://server/isotoma/example/master/index.html

If your pages link relatively to each other then this should be sufficient.

Creating and maintaining the password file
------------------------------------------

Check out the repository and change into the html-templates directory, then::

    htpasswd -bc passwd <username> <password>

Will create a password file called `passwd` with that user in it.  The `-c`
option creates a new file and `-b` means the password is specified on the
command line.

Then add the file to the repository and push it.

MIME Types
----------

htmlhub guesses the mime types of files based on the contents of the file
/etc/mime.types.  This means it works pretty much like Apache in terms of what
it can serve, and how it serves those files.

