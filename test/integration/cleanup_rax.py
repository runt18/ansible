#!/usr/bin/env python

import os
import re
import yaml
import argparse

try:
    import pyrax
    HAS_PYRAX = True
except ImportError:
    HAS_PYRAX = False


def rax_list_iterator(svc, *args, **kwargs):
    method = kwargs.pop('method', 'list')
    items = getattr(svc, method)(*args, **kwargs)
    while items:
        retrieved = getattr(svc, method)(*args, marker=items[-1].id, **kwargs)
        if items and retrieved and items[-1].id == retrieved[0].id:
            del items[-1]
        items.extend(retrieved)
        if len(retrieved) < 2:
            break
    return items


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('-y', '--yes', action='store_true', dest='assumeyes',
                        default=False, help="Don't prompt for confirmation")
    parser.add_argument('--match', dest='match_re',
                        default='^ansible-testing',
                        help='Regular expression used to find resources '
                             '(default: %(default)s)')

    return parser.parse_args()


def authenticate():
    try:
        with open(os.path.realpath('./credentials.yml')) as f:
            credentials = yaml.load(f)
    except Exception as e:
        raise SystemExit(e)

    try:
        pyrax.set_credentials(credentials.get('rackspace_username'),
                              credentials.get('rackspace_api_key'))
    except Exception as e:
        raise SystemExit(e)


def prompt_and_delete(item, prompt, assumeyes):
    if not assumeyes:
        assumeyes = raw_input(prompt).lower() == 'y'
    assert (hasattr(item, 'delete') or hasattr(item, 'terminate'),
            "Class <{0!s}> has no delete or terminate attribute".format(item.__class__))
    if assumeyes:
        if hasattr(item, 'delete'):
            item.delete()
            print ("Deleted {0!s}".format(item))
        if hasattr(item, 'terminate'):
            item.terminate()
            print ("Terminated {0!s}".format(item))


def delete_rax(args):
    """Function for deleting CloudServers"""
    print ("--- Cleaning CloudServers matching '{0!s}'".format(args.match_re))
    search_opts = dict(name='^{0!s}'.format(args.match_re))
    for region in pyrax.identity.services.compute.regions:
        cs = pyrax.connect_to_cloudservers(region=region)
        servers = rax_list_iterator(cs.servers, search_opts=search_opts)
        for server in servers:
            prompt_and_delete(server,
                              'Delete matching {0!s}? [y/n]: '.format(server),
                              args.assumeyes)


def delete_rax_clb(args):
    """Function for deleting Cloud Load Balancers"""
    print ("--- Cleaning Cloud Load Balancers matching '{0!s}'".format(args.match_re))
    for region in pyrax.identity.services.load_balancer.regions:
        clb = pyrax.connect_to_cloud_loadbalancers(region=region)
        for lb in rax_list_iterator(clb):
            if re.search(args.match_re, lb.name):
                prompt_and_delete(lb,
                                  'Delete matching {0!s}? [y/n]: '.format(lb),
                                  args.assumeyes)


def delete_rax_keypair(args):
    """Function for deleting Rackspace Key pairs"""
    print ("--- Cleaning Key Pairs matching '{0!s}'".format(args.match_re))
    for region in pyrax.identity.services.compute.regions:
        cs = pyrax.connect_to_cloudservers(region=region)
        for keypair in cs.keypairs.list():
            if re.search(args.match_re, keypair.name):
                prompt_and_delete(keypair,
                                  'Delete matching {0!s}? [y/n]: '.format(keypair),
                                  args.assumeyes)


def delete_rax_network(args):
    """Function for deleting Cloud Networks"""
    print ("--- Cleaning Cloud Networks matching '{0!s}'".format(args.match_re))
    for region in pyrax.identity.services.network.regions:
        cnw = pyrax.connect_to_cloud_networks(region=region)
        for network in cnw.list():
            if re.search(args.match_re, network.name):
                prompt_and_delete(network,
                                  'Delete matching {0!s}? [y/n]: '.format(network),
                                  args.assumeyes)


def delete_rax_cbs(args):
    """Function for deleting Cloud Networks"""
    print ("--- Cleaning Cloud Block Storage matching '{0!s}'".format(args.match_re))
    for region in pyrax.identity.services.network.regions:
        cbs = pyrax.connect_to_cloud_blockstorage(region=region)
        for volume in cbs.list():
            if re.search(args.match_re, volume.name):
                prompt_and_delete(volume,
                                  'Delete matching {0!s}? [y/n]: '.format(volume),
                                  args.assumeyes)


def delete_rax_cdb(args):
    """Function for deleting Cloud Databases"""
    print ("--- Cleaning Cloud Databases matching '{0!s}'".format(args.match_re))
    for region in pyrax.identity.services.database.regions:
        cdb = pyrax.connect_to_cloud_databases(region=region)
        for db in rax_list_iterator(cdb):
            if re.search(args.match_re, db.name):
                prompt_and_delete(db,
                                  'Delete matching {0!s}? [y/n]: '.format(db),
                                  args.assumeyes)


def main():
    if not HAS_PYRAX:
        raise SystemExit('The pyrax python module is required for this script')

    args = parse_args()
    authenticate()

    funcs = [f for n, f in globals().items() if n.startswith('delete_rax')]
    for func in sorted(funcs, key=lambda f: f.__name__):
        try:
            func(args)
        except Exception as e:
            print ("---- {0!s} failed ({1!s})".format(func.__name__, e.message))


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print ('\nExiting...')
