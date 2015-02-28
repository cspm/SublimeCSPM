# SublimeCSPM

This bundle adds support for CSPM syntax highlighting to
[Sublime Text](https://www.sublimetext.com) and
[TextMate 2](http://macromates.com).

It also includes some simple commands to typecheck the current file, open the
current file in FDR3, and check all assertions using command line version of
FDR.
  
## Installation

To install the plugin for Sublime Text, use
[Package Control](https://packagecontrol.io) and install the package named
``CSPM``.

To install this plugin in TextMate 2:

    mkdir -p ~/Library/Application\ Support/Avian/Pristine\ Copy/Bundles
    cd ~/Library/Application\ Support/Avian/Pristine\ Copy/Bundles
    git clone git://github.com/cspm/cspm.tmbundle cspm.tmbundle

## Commands

The package adds three commands to Sublime Text.

* Check Assertions (alt-shift-c): checks all assertions using the command line
  version of FDR.
* Briefly Check Assertions (alt-shift-b): this behaves like the Check Assertions
  command, but only gives the result of each refinement check, and does not
  give any counterexamples or log information.
* Open in FDR (alt-shift-r): opens the current file in FDR.
* Typecheck (alt-shift-t): typechecks the current file.

Sometimes the current file will not be suitable for typechecking on its own
(e.g. if ``a.csp`` includes ``b.csp``, but ``b.csp`` depends on declarations in
``a.csp``). In such cases, it is possible to specify the *root file* that should
be loaded by FDR instead by altering the first line to, e.g. ``-- root: a.csp``.
In such cases FDR will find type errors in all files that are included by the
root file.

## Settings

Sublime Text can be configured using the following options.

* ``fdr_bin_dir`` (defaults to null): sets the directory in which the plugin
  will look for ``fdr3`` and ``refines``. By default, the plugin will search in
  the normal installation locations.
* ``typecheck_on_save`` (defaults to true): if set, the typechecker will
  automatically be executed whenever a CSP file is saved.

Settings may also be set on a per-project basis by adding a "cspm" dictionary
to the project settings. For example, adding:

    "cspm": {
        "typecheck_on_save": true
    }

will override the ``typecheck_on_save`` setting just for the particular project.

## License

See LICENSE.
