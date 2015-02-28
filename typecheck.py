import sublime, sublime_plugin
import json, os, platform, time, subprocess

def settings_get(name, default=None):
    plugin_settings = sublime.load_settings('CSPM.sublime-settings')
    project_settings = None
    if sublime.active_window() and sublime.active_window().active_view():
        project_settings = sublime.active_window().active_view().settings().get("cspm")

    if project_settings is None:
        project_settings = {}

    setting = project_settings.get(name, plugin_settings.get(name, default))
    return setting

def is_mac():
    return platform.system() == "Darwin"
def is_linux():
    return platform.system() == "Linux"
def is_windows():
    return platform.system() == "Windows"

def split_range(string):
    """Creates a range from a string of the form x-y. If the string contains no
       -, the range is assumed to be a point.
    """
    if string == "<unknown location>":
        return None
    minus = string.find("-")
    if minus == -1:
        return int(string), int(string)
    else:
        return int(string[:minus]), int(string[minus+1:])

def get_root_csp_file(view):
    """ Computes the file that typehchecking etc should be started from for
        the given view.
    """
    first_line = view.substr(view.line(0))
    prefix_marker = "-- root: "
    if first_line.startswith(prefix_marker):
        root_file = first_line[len(prefix_marker):].strip()
        current_file_dir = os.path.dirname(view.file_name())
        return os.path.abspath(os.path.join(current_file_dir, root_file))
    else:
        return view.file_name()

def process_startup_info():
    # Don't flash a terminal window under Windows
    startupinfo = None
    if is_windows():
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    return startupinfo

def is_cspm_view(view):
    """ True if the view has a cspm file loaded"""
    if view is None or view.file_name() is None:
        return False
    return 'cspm' in view.settings().get('syntax').lower()

class CspmInsertTextCommand(sublime_plugin.TextCommand):
    """ A helper command to insert text at the end of a buffer.
    """
    def run(self, edit, txt, scroll_to_end):
        self.view.insert(edit, self.view.size(), txt);
        self.view.show(self.view.size())

class CspmRunTypecheckerCommand(sublime_plugin.WindowCommand):
    """ Runs FDR's typechecker on the active file.
    """
    def is_enabled(self):
        return is_cspm_view(self.window.active_view())

    def run(self):
        self._unmark_errors()

        view = self.window.active_view()
        if view is None:
            return
        self.window.run_command("hide_panel", {"panel": "output.textarea"})
        output_view = self.window.get_output_panel("textarea")

        typechecker_output = self._run_typechecker(get_root_csp_file(view))
        if typechecker_output is not None:
            sublime.status_message("FDR: errors found")
            output_view.set_read_only(False)
            output_view.settings().set('result_file_regex', '^(.*?):(\d+)')
            output_view.run_command('cspm_insert_text', {
                    "txt": typechecker_output.strip(),
                    "scroll_to_end": False,
                })
            output_view.set_read_only(True)
            output_view.show(0)
            self.window.run_command("show_panel", {"panel": "output.textarea"})
            self._mark_errors(typechecker_output)
        else:
            sublime.status_message("FDR: no errors found")

    def _run_typechecker(self, file_name):
        process = subprocess.Popen([
                find_fdr_program('refines'), '--typecheck', file_name,
            ], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd='/',
            startupinfo=process_startup_info())
        output, _ = process.communicate()
        if process.returncode == 0:
            return None
        return output.decode('utf-8')

    def _mark_errors(self, output):
        output_lines = output.split("\n")
        errors = []
        current_error = None
        for oline in output_lines:
            if oline == "":
                continue
            if "Too many errors generated" in oline:
                continue

            if current_error is None or not oline.startswith("    "):
                # Must be a filename
                if current_error is not None:
                    errors.append(current_error)
                current_error = None

                line_len = len(oline)
                col_start = oline.rfind(":", 0, line_len-1)
                line_num_pos = oline.rfind(":", 0, col_start)
                current_error = {
                        'column': split_range(oline[col_start+1:line_len-1]),
                        'line': split_range(oline[line_num_pos+1:col_start]),
                        'filename': oline[:line_num_pos],
                        'contents': "",
                    }
            else:
                current_error['contents'] += oline[4:] + "\n"

        if current_error is not None:
            errors.append(current_error)

        views = {}
        regions = {}
        for error in errors:
            view = self.window.find_open_file(error["filename"])
            if view == None or error["line"] is None:
                continue
            start_line, end_line = error["line"]
            start_col, end_col = error["column"]
            # Sublime row/col numbers are all 0-based
            start_pos = view.text_point(start_line-1, start_col-1)
            end_pos = view.text_point(end_line-1, end_col-1)
            region = sublime.Region(start_pos, end_pos)
            views[view.id()] = view
            if not regions.get(view.id()):
                regions[view.id()] = []
            regions[view.id()].append(region)

        for view in views:
            self._mark_error(views[view], regions[view])

    def _mark_error(self, view, regions):
        view.add_regions('error', regions, 'invalid', 'dot',
            sublime.DRAW_OUTLINED)

    def _unmark_errors(self):
        for view in self.window.views():
            view.erase_regions('error')

class CspmRunFdrCommand(sublime_plugin.WindowCommand):
    """ Opens FDR will the active file loaded
    """
    def is_enabled(self):
        return is_cspm_view(self.window.active_view())

    def run(self):
        view = self.window.active_view()
        if view is None:
            return
        fdr = find_fdr_program("fdr3")
        if is_mac() and "FDR3.app" in fdr:
            # Open as an application bundle
            fdr_app, _ = os.path.split(os.path.split(os.path.split(fdr)[0])[0])
            subprocess.Popen(["open", "-a", fdr_app, get_root_csp_file(view)])
        else:
            subprocess.Popen([fdr, get_root_csp_file(view)])

class CspmCheckAssertionsCommand(sublime_plugin.WindowCommand):
    """ Checks all assertions in the active file.
        brief can be set to suppress logs and counterexamples.
    """
    def is_enabled(self):
        return is_cspm_view(self.window.active_view())

    def run(self, brief=False):
        view = self.window.active_view()
        if view is None:
            return
        self.window.run_command("hide_panel", {"panel": "output.textarea"})
        self.output_view = self.window.get_output_panel("textarea")
        self.output_view.set_read_only(True)
        self.window.run_command("show_panel", {"panel": "output.textarea"})
        self._check_assertions(get_root_csp_file(view), brief)
    
    def _check_assertions(self, file_name, brief):
        def runner():
            arguments = [find_fdr_program('refines'), "--format=plain"]
            if brief:
                arguments += ["--brief", "--quiet"]
            process = subprocess.Popen(arguments+[file_name],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd='/',
                startupinfo=process_startup_info())
            for line in iter(process.stdout.readline, b''):
                self.output_view.set_read_only(False)
                self.output_view.run_command('cspm_insert_text', {
                        "txt": line.decode("utf-8"),
                        "scroll_to_end": True,
                    })
                self.output_view.set_read_only(True)
                if not self.output_view.window():
                    sublime.status_message("FDR: cancelled")
                    process.kill()
            self.output_view.set_read_only(False)
            process.communicate()

        sublime.set_timeout_async(runner, 0)

class EventHandler(sublime_plugin.EventListener):
    def on_post_save(self, view):
        if not is_cspm_view(view):
            return
        if settings_get('typecheck_on_save', True):
            view.window().run_command("cspm_run_typechecker")

def find_fdr_program(program):
    def is_exe(fpath):
        return os.path.isfile(fpath) and os.access(fpath, os.X_OK)

    search_paths = []
    setting_path = settings_get("fdr_bin_dir", None)
    if setting_path is not None:
        search_paths.append(setting_path)

    if is_mac():
        search_paths += [
            "/Applications/FDR3.app/Contents/MacOS",
            "~/Applications/FDR3.app/Contents/MacOS",
        ]
    elif is_windows():
        program += ".exe"
        search_paths += [
            "C:\\Program Files\\FDR\\bin"
        ]
    elif is_linux():
        search_paths += os.getenv("PATH").split(os.pathsep)
        search_paths += ["/opt/fdr/bin"]

    for path in search_paths:
        path = path.strip('"')
        exe_file = os.path.join(os.path.expanduser(path), program)
        if is_exe(exe_file):
            return exe_file

    raise Exception("Cannot find %s executable in %s. Please set fdr_bin_dir." \
        % (program, search_paths))
