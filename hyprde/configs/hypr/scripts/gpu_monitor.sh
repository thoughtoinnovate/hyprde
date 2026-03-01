#!/bin/bash
radeontop -d - -l 1|grep gpu|awk -F',' '{print $2}'|awk -F'gpu' '{print $2}'|sed 's/^[ \t]*//;s/[ \t]*$//'
