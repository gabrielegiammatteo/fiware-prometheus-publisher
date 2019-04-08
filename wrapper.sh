#!/bin/sh


configDir="/etc/ceilometer"
configFile=${configFile:-"${configDir}/ceilometer.conf"}

debug=${fipromDebug:-"false"}
pushGatewayUrl=${fipromPushGatewayUrl:-"http://localhost:9091/metrics/job/fiprom"}
converterFile=${fipromConverterFile:-"${configDir}/fiprom-converter.yaml"}
namesFile=${fipromNamesFile:-"/fiprom-names"}
groupsFile=${fipromGroupsFile:-"/fiprom-groups"}
cacheFile=${fipromCacheFile:-"/tmp/cache"}
staleTimeout=${fipromStaleTimeout:-3600}
logFile=${fipromLogFile:-""}
rabbitmqHost=${fipromRabbitMQHost:-""}
rabbitmqUser=${fipromRabbitMQUser:-""}
rabbitmqPassword=${fipromRabbitMQPassword:-""}
meteringSecret=${fipromMeteringSecret:-""}


if [ ! -e "${configFile}" ]; then
    mkdir -p ${configDir}
    cp ceilometer.conf.example ${configFile}

    sed -i "s|VAR_DEBUG|${debug}|g"                         ${configFile}
    sed -i "s|VAR_PUSHGATEWAY_URL|${pushGatewayUrl}|g"      ${configFile}
    sed -i "s|VAR_CONVERTER_FILE|${converterFile}|g" 		${configFile}
    sed -i "s|VAR_NAMES_FILE|${namesFile}|g" 				${configFile}
    sed -i "s|VAR_GROUPS_FILE|${groupsFile}|g" 				${configFile}
    sed -i "s|VAR_CACHE_FILE|${cacheFile}|g" 				${configFile}
    sed -i "s|VAR_STALE_TIMEOUT|${staleTimeout}|g"	 		${configFile}
    sed -i "s|VAR_LOG_FILE|${logFile}|g" 	                ${configFile}
    sed -i "s|VAR_RABBITMQ_URL|${rabbitmqHost}|g" 	        ${configFile}
    sed -i "s|VAR_RABBITMQ_USER|${rabbitmqUser}|g" 	        ${configFile}
    sed -i "s|VAR_RABBITMQ_PASSWORD|${rabbitmqPassword}|g" 	${configFile}
    sed -i "s|VAR_METERING_SECRET|${meteringSecret}|g" 	    ${configFile}

    sed -i 's/VAR_.*//g'    ${configFile}

fi


if [ ! -e "${converterFile}" ]; then
    cp fiprom_converter_conf.yaml ${converterFile}
fi


cat ${configFile}

exec ceilometer-collector --config-file ${configFile}
