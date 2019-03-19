# Fiware Prometheus Publisher
A Ceilometer (Kilo) publisher that converts Ceilometer samples to Prometheus dimensions, flexibly mapping dimensions to labels and enriching the Prometheus metrics with object names (e.g. users, tenants, hosts) instead of the ids available in Ceilometer samples. Metrics generated are pushed to an external [Prometheus Push Gateway](https://github.com/prometheus/pushgateway).

It is inspired by the Prometheus publisher included in the official Ceilometer distribution, starting from Newton. The component has been primarily implemented to collect metrics in the FIWARE Vicenza node infrastructure


## Installation
This component is distributed through PYPI. Install it with:
```bash
pip intall fiware-prometheu-publsiher
```

## Configuration
Before starting using this publisher, it must be added in the pipeline of Ceilometer by changing the configuration of `pipeline.yaml` file. In the `publishers` section add:

```yaml
- publishers:
  - fiprom://<url>?<query_params>
```
where:

- *fiprom* is the label that identifies the publisher
- *url* is the URL (without the protocol) of the Push Gateway where to push metrics. As explained [here](https://github.com/prometheus/pushgateway#url) the *url* might contain custom static labels that will be added to all metrics by the Push Gateway (e.g. `/metrics/job/ceilometer/infrastructure/fiware`)
- *query_params* is a query-string style list of parameters passed to the publisher.

There are four main parameters to set (see subsections for details):

- `converter_config_file`: the configuration file that defines how samples should be converted into Prometheus labels (default: `/opt/fiprom_converter_conf`)
- `cache_file`: the file where the publisher keeps its cache of instance labels. It must be accessible in read and write modes (default: `/tmp/fiprom_cache`).
- `names_file`: the file where the publisher reads the id <-> names mapping for users, hosts and tenants (default: `/opt/fiprom_names`).
- `tenant_group_file`: the name of the file  where the publisher reads a custom group for each tenant (default: `/opt/fiprom_groups`)

For instance:
```ini
- publishers:
  - fiprom://localhost:9091/metrics/job/ceilometer/infrastructure/fiware?converter_conf_file=/home/fiware/fiprom_converter.yaml&names_file=/home/fiware/names.conf

```
Other HTTP connection related parameters are accepted (e.g. max parallel requests, timeout time, max retries). See `util.py` for details.

### Converter Config file
This is a mandatory configuration file for the publisher that describes how Ceilometer samples should be converted in Prometheus metrics. The file is in YAML format and follows this schema:
```yaml

name_mapping: <python expression>

labels:
  - <sample_name_pattern>:
    <label_name>: <python expression>
```

A working configuration with detailed comments can be found at `conf/firpom_converter_conf.yaml`.

### Names file

The *names_file* contains the mapping between Opentack IDs and objects names. Since metrics created by Ceilometer only contain IDs of objects, this mapping file is required to add label with names (more human readable) to Prometheus metrics.

The file must contain one mapping for each line in the format:
```ini
<id> <delimiter> <name>
```
'=' or ':' characters are used as delimiter if found in the row, otherwise space, tab or comma characters are used. All of these are valid lines:
```ini
acede503-78e4-49cf-adbc-bd87390d4f6a helloworld
4c9e370ae557689709a64e9b543d50fd0f1538d0c5a22ac30c5afb41,  host1.eng.it
f7eb45f96d62423a805bd2ee5734d961: admin
f00a0cba70174563b6deef58dffebda2 = This is a demo, project 
```

### Tenant Group file
The *tenant_group_file* is used to assign a group to each tenant. The file is in the format:
```ini
<tenant_id_or_name> <delimiter> <group>
```


