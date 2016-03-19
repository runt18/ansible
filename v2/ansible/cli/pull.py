# (c) 2012, Michael DeHaan <michael.dehaan@gmail.com>
#
# This file is part of Ansible
#
# Ansible is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Ansible is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Ansible.  If not, see <http://www.gnu.org/licenses/>.

########################################################
import datetime
import os
import random
import shutil
import socket

from ansible import constants as C
from ansible.errors import AnsibleError, AnsibleOptionsError
from ansible.cli import CLI
from ansible.utils.display import Display
from ansible.utils.vault import read_vault_file

########################################################

class PullCLI(CLI):
    ''' code behind ansible ad-hoc cli'''

    DEFAULT_REPO_TYPE = 'git'
    DEFAULT_PLAYBOOK = 'local.yml'
    PLAYBOOK_ERRORS = {
        1: 'File does not exist',
        2: 'File is not readable'
    }
    SUPPORTED_REPO_MODULES = ['git']

    def parse(self):
        ''' create an options parser for bin/ansible '''

        self.parser = CLI.base_parser(
            usage='%prog <host-pattern> [options]',
            connect_opts=True,
            vault_opts=True,
        )

        # options unique to pull
        self.parser.add_option('--purge', default=False, action='store_true', help='purge checkout after playbook run')
        self.parser.add_option('-o', '--only-if-changed', dest='ifchanged', default=False, action='store_true',
            help='only run the playbook if the repository has been updated')
        self.parser.add_option('-s', '--sleep', dest='sleep', default=None,
            help='sleep for random interval (between 0 and n number of seconds) before starting. This is a useful way to disperse git requests')
        self.parser.add_option('-f', '--force', dest='force', default=False, action='store_true',
            help='run the playbook even if the repository could not be updated')
        self.parser.add_option('-d', '--directory', dest='dest', default=None, help='directory to checkout repository to')
        self.parser.add_option('-U', '--url', dest='url', default=None, help='URL of the playbook repository')
        self.parser.add_option('-C', '--checkout', dest='checkout',
            help='branch/tag/commit to checkout.  ' 'Defaults to behavior of repository module.')
        self.parser.add_option('--accept-host-key', default=False, dest='accept_host_key', action='store_true',
            help='adds the hostkey for the repo url if not already added')
        self.parser.add_option('-m', '--module-name', dest='module_name', default=self.DEFAULT_REPO_TYPE,
            help='Repository module name, which ansible will use to check out the repo. Default is {0!s}.'.format(self.DEFAULT_REPO_TYPE))


        self.options, self.args = self.parser.parse_args()

        if self.options.sleep:
            try:
                secs = random.randint(0,int(self.options.sleep))
                self.options.sleep = secs
            except ValueError:
                raise AnsibleOptionsError("{0!s} is not a number.".format(self.options.sleep))

        if not self.options.url:
            raise AnsibleOptionsError("URL for repository not specified, use -h for help")

        if len(self.args) != 1:
            raise AnsibleOptionsError("Missing target hosts")

        if self.options.module_name not in self.SUPPORTED_REPO_MODULES:
            raise AnsibleOptionsError("Unsuported repo module {0!s}, choices are {1!s}".format(self.options.module_name, ','.join(self.SUPPORTED_REPO_MODULES)))

        self.display.verbosity = self.options.verbosity
        self.validate_conflicts()

    def run(self):
        ''' use Runner lib to do SSH things '''

        # log command line
        now = datetime.datetime.now()
        self.display.display(now.strftime("Starting Ansible Pull at %F %T"))
        self.display.display(' '.join(sys.argv))

        # Build Checkout command
        # Now construct the ansible command
        limit_opts = 'localhost:{0!s}:127.0.0.1'.format(socket.getfqdn())
        base_opts = '-c local --limit "{0!s}"'.format(limit_opts)
        if self.options.verbosity > 0:
            base_opts += ' -{0!s}'.format(''.join([ "v" for x in range(0, self.options.verbosity) ]))

        # Attempt to use the inventory passed in as an argument
        # It might not yet have been downloaded so use localhost if note
        if not self.options.inventory or not os.path.exists(self.options.inventory):
            inv_opts = 'localhost,'
        else:
            inv_opts = self.options.inventory

        #TODO: enable more repo modules hg/svn?
        if self.options.module_name == 'git':
            repo_opts = "name={0!s} dest={1!s}".format(self.options.url, self.options.dest)
            if self.options.checkout:
                repo_opts += ' version={0!s}'.format(self.options.checkout)

            if self.options.accept_host_key:
                repo_opts += ' accept_hostkey=yes'

            if self.options.key_file:
                repo_opts += ' key_file={0!s}'.format(options.key_file)

        path = utils.plugins.module_finder.find_plugin(options.module_name)
        if path is None:
            raise AnsibleOptionsError(("module '{0!s}' not found.\n".format(options.module_name)))

        bin_path = os.path.dirname(os.path.abspath(__file__))
        cmd = '{0!s}/ansible localhost -i "{1!s}" {2!s} -m {3!s} -a "{4!s}"'.format(
            bin_path, inv_opts, base_opts, self.options.module_name, repo_opts
        )

        for ev in self.options.extra_vars:
            cmd += ' -e "{0!s}"'.format(ev)

        # Nap?
        if self.options.sleep:
            self.display.display("Sleeping for {0:d} seconds...".format(self.options.sleep))
            time.sleep(self.options.sleep);

        # RUN the Checkout command
        rc, out, err = cmd_functions.run_cmd(cmd, live=True)

        if rc != 0:
            if self.options.force:
                self.display.warning("Unable to update repository. Continuing with (forced) run of playbook.")
            else:
                return rc
        elif self.options.ifchanged and '"changed": true' not in out:
            self.display.display("Repository has not changed, quitting.")
            return 0

        playbook = self.select_playbook(path)

        if playbook is None:
            raise AnsibleOptionsError("Could not find a playbook to run.")

        # Build playbook command
        cmd = '{0!s}/ansible-playbook {1!s} {2!s}'.format(bin_path, base_opts, playbook)
        if self.options.vault_password_file:
            cmd += " --vault-password-file={0!s}".format(self.options.vault_password_file)
        if self.options.inventory:
            cmd += ' -i "{0!s}"'.format(self.options.inventory)
        for ev in self.options.extra_vars:
            cmd += ' -e "{0!s}"'.format(ev)
        if self.options.ask_sudo_pass:
            cmd += ' -K'
        if self.options.tags:
            cmd += ' -t "{0!s}"'.format(self.options.tags)

        os.chdir(self.options.dest)

        # RUN THE PLAYBOOK COMMAND
        rc, out, err = cmd_functions.run_cmd(cmd, live=True)

        if self.options.purge:
            os.chdir('/')
            try:
                shutil.rmtree(options.dest)
            except Exception, e:
                print >>sys.stderr, "Failed to remove {0!s}: {1!s}".format(options.dest, str(e))

        return rc


    def try_playbook(self, path):
        if not os.path.exists(path):
            return 1
        if not os.access(path, os.R_OK):
            return 2
        return 0

    def select_playbook(self, path):
        playbook = None
        if len(self.args) > 0 and self.args[0] is not None:
            playbook = os.path.join(path, self.args[0])
            rc = self.try_playbook(playbook)
            if rc != 0:
                self.display.warning("{0!s}: {1!s}".format(playbook, self.PLAYBOOK_ERRORS[rc]))
                return None
            return playbook
        else:
            fqdn = socket.getfqdn()
            hostpb = os.path.join(path, fqdn + '.yml')
            shorthostpb = os.path.join(path, fqdn.split('.')[0] + '.yml')
            localpb = os.path.join(path, DEFAULT_PLAYBOOK)
            errors = []
            for pb in [hostpb, shorthostpb, localpb]:
                rc = self.try_playbook(pb)
                if rc == 0:
                    playbook = pb
                    break
                else:
                    errors.append("{0!s}: {1!s}".format(pb, self.PLAYBOOK_ERRORS[rc]))
            if playbook is None:
                self.display.warning("\n".join(errors))
            return playbook
