# fiware-prometheus-publisher
A Ceilometer (Kilo) publisher implemented to collect metrics in the FIWARE Vicenza node infrastructure


## Installation
This component is distributed through PYPI. Install with:
```bash
pip intall fiware-prometheu-publsiher
```

## Configuration
The component installs a new publsiher for Ceilometer, therefore Ceilometer must be configured to use it. In the`publishers` section of the *pipeline.yaml* file add:
```yaml
- publishers:
  - fiprom://<url>?<query_params>
```
The accepted query parameters accepted are:
- `cache_file`: the name of the file where the publisher keep its cache of instance labels. It must be accessible in read and write modes (default: `/tmp/fiprom_publisher_cache`).
- `names_file`: the name of the file where the publisher reads the id <-> names mapping for users, hosts and tenants (default: `/tmp/fiprom_publisher_names`).
- `tenant_group_file`: the name of the file  where the publisher reads the group for each tenant (default: `/tmp/fiprom_publisher_tenant_group`)

Other HTTP connection related parameters are accepted (e.g. max parallel requests, timeout time, max retries). See `util.py` for details.
### Names file

The *names_file* contains the mapping between Opentack IDs and their names. Since metrics created by Ceilometer only contain IDs of objects, we need this mapping to add label with names (more human readable) to Prometheus metrics.

The file must contain one mapping for each line in the format:
```ini
<id> <delimiter> <name>
```
'=' or ':' characters are used as delimiter if found in the row, otherwise space, tab or comma characters are used. All of these are valid lines:
```ini
acede503-78e4-49cf-adbc-bd87390d4f6a helloworld
4c9e370ae557689709a64e9b543d50fd0f1538d0c5a22ac30c5afb41   ,   host1.eng.it
f7eb45f96d62423a805bd2ee5734d961: admin
f00a0cba70174563b6deef58dffebda2   = This is a demo, project 
```

### Tenant Group file
The *tenant_group_file* is used to assign a group to each tenant. The file is in the format:
```ini
<tenant_id_or_name> <delimiter> <group>
```

