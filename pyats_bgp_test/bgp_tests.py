#!/bin/env python

# To get a logger for the script
import logging
import json
# To build the table at the end
from tabulate import tabulate

# Needed for aetest script
from pyats import aetest
from pyats.log.utils import banner

# Genie Imports
from genie.conf import Genie
from genie.abstract import Lookup

# import the genie libs
from genie.libs import ops # noqa

import os
import hvac

# Get your logger for your script
log = logging.getLogger(__name__)


###################################################################
#                  COMMON SETUP SECTION                           #
###################################################################

# Function to get credentials from HashiCorp Vault
def get_vault_secrets():
    # try:
    client = hvac.Client(url=os.environ['VAULT_ADDR'], 
                        token=os.environ['VAULT_TOKEN'], verify=False)

    if not client.is_authenticated():
        # self.failed("Error: Vault Authentication Failed!")
        raise VaultAuthError("Error: Vault Authentication Failed!") 
    else:
        response = client.secrets.kv.v2.read_secret_version(path='cml_devices_secrets', mount_point='cml_secrets')
        username = response['data']['data']['iosxr_username']
        password = response['data']['data']['iosxr_password']

        return username, password
        
    # except Exception as e:
    #     self.failed("Error: Vault Authentication Failed!")
            
class common_setup(aetest.CommonSetup):
    """ Common Setup section """

    # CommonSetup have subsection.
    # You can have 1 to as many subsection as wanted
    
    @aetest.subsection
    def connect(self, testbed):
        # Load testbed
        # self.testbed = loader.load(testbed)
        genie_testbed = Genie.init(testbed)
        self.parent.parameters['testbed'] = genie_testbed

        # Get credentials from Vault
        username, password = get_vault_secrets()

        # Apply credentials to testbed
        device_list = []
        # for device in self.testbed.devices.values():
        for device in genie_testbed.devices.values():
            device.credentials['default'] = {
                'username': username,
                'password': password
            }
            try:
                device.connect()
            except Exception as e:
                self.failed("Failed to establish connection to '{}'".format(
                    device.name))

            device_list.append(device)

        # Pass list of devices the to testcases
        self.parent.parameters.update(dev=device_list)
        

    # # Connect to each device in the testbed
    # @aetest.subsection
    # def connect(self, testbed):
    #     genie_testbed = Genie.init(testbed)
    #     self.parent.parameters['testbed'] = genie_testbed
    #     device_list = []
    #     for device in genie_testbed.devices.values():
    #         log.info(banner(
    #             "Connect to device '{d}'".format(d=device.name)))
    #         try:
    #             device.connect()
    #         except Exception as e:
    #             self.failed("Failed to establish connection to '{}'".format(
    #                 device.name))

    #         device_list.append(device)

    #     # Pass list of devices the to testcases
    #     self.parent.parameters.update(dev=device_list)


###################################################################
#                     TESTCASES SECTION                           #
###################################################################


class BgpNeighborsTest(aetest.Testcase):
    """ This is user Testcases section """

    # First test section
    @ aetest.test
    def learn_bgp(self):
        """ Sample test section. Only print """

        self.all_bgp_sessions = {}
        for dev in self.parent.parameters['dev']:
            log.info(banner("Gathering BGP Information from {}".format(
                dev.name)))
            abstract = Lookup.from_device(dev)
            bgp = abstract.ops.bgp.bgp.Bgp(dev)
            bgp.learn()
            if hasattr(bgp, 'info'):
                self.all_bgp_sessions[dev.name] = bgp.info
            else:
                self.failed("Failed to learn BGP info from device %s" % dev.name, 
                            goto=['common_cleanup'])

    @ aetest.test
    def check_bgp(self):
        """ Sample test section. Only print """

        failed_dict = {}
        mega_tabular = []
        for device, bgp in self.all_bgp_sessions.items():

            # may need to change based on BGP config
            vrfs_dict = bgp['instance']['default']['vrf']

            for vrf_name, vrf_dict in vrfs_dict.items():

                # If no neighbor for default VRF, then set the neighbors value to {}
                neighbors = vrf_dict.get('neighbor', {})
                for nbr, props in neighbors.items():
                    state = props.get('session_state')
                    if state:
                        tr = []
                        tr.append(vrf_name)
                        tr.append(nbr)
                        tr.append(state)
                        if state.lower() == 'established':
                            tr.append('Passed')
                        else:
                            failed_dict[device] = {}
                            failed_dict[device][nbr] = props
                            tr.append('Failed')

                        mega_tabular.append(tr)

                log.info("Device {d} Table:\n".format(d=device))
                log.info(tabulate(mega_tabular,
                                  headers=['VRF', 'Peer',
                                           'State', 'Pass/Fail'],
                                  tablefmt='orgtbl'))

        if failed_dict:
            log.error(json.dumps(failed_dict, indent=3))
            self.failed("Testbed has BGP Neighbors that are not established")

        else:
            self.passed("All BGP Neighbors are established")

#####################################################################
####                       COMMON CLEANUP SECTION                 ###
#####################################################################


# This is how to create a CommonCleanup
# You can have 0 , or 1 CommonCleanup.
# CommonCleanup can be named whatever you want :)
class common_cleanup(aetest.CommonCleanup):
    """ Common Cleanup for Sample Test """

    # CommonCleanup follow exactly the same rule as CommonSetup regarding
    # subsection
    # You can have 1 to as many subsections as wanted
    # here is an example of 1 subsection

    @aetest.subsection
    def clean_everything(self):
        """ Common Cleanup Subsection """
        log.info("Aetest Common Cleanup ")


if __name__ == '__main__':  # pragma: no cover
    # aetest.main()
    from pyats.topology import loader

    # Load the testbed file
    testbed = loader.load("cml_testbed.yaml")

    # and pass all arguments to aetest.main() as kwargs
    aetest.main(testbed=testbed)

    # To run standalone execution:
    # python bgp_tests.py