# To run the job:
# pyats run job bgp_test_job.py --testbed-file cml_testbed.yaml
# Description: This job file checks that all BGP neighbors are in Established state
import os

# All run() must be inside a main function
def main(runtime):
    # Find the location of the script in relation to the job file
    bgp_tests = os.path.join(os.path.dirname(__file__), 
                             'bgp_tests.py')
    # Execute the testscript
    runtime.tasks.run(testscript=bgp_tests)
    