#!/bin/bash

#https://www.intel.com/content/www/us/en/support/articles/000058107/processors/intel-xeon-processors.html
curl https://repositories.intel.com/dcdt/dcdiag.pub | sudo apt-key add -
sudo apt-add-repository 'deb [arch=amd64] https://repositories.intel.com/dcdt/debian stable main'

sudo apt-get update
sudo apt-get install dcdiag

