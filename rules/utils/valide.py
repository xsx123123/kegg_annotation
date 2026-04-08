def load_user_config(config, cmd_arg_name="user_yaml") -> None:
    """
    Parse the configuration file path passed from the command line and merge it into the current config.

    Args:
        config (dict): Snakemake's global config object
        cmd_arg_name (str): The key name after --config in command line, defaults to "user_yaml"
    """
    custom_path = config.get(cmd_arg_name)

    # If the user didn't pass this parameter, return directly and use the default configuration
    if not custom_path:
        return

    # Check if the file exists
    if not os.path.exists(custom_path):
        print(f"\n\033[91m[Config Error] Cannot find the specified user configuration file: {custom_path}\033[0m\nPlease check if the path is correct.\n", file=sys.stderr)
        sys.exit(1)

    # Load and merge configuration
    print(f"\033[92m[Config Info] Loading external project configuration: {custom_path}\033[0m")
    
    try:
        with open(custom_path, 'r') as f:
            custom_data = yaml.safe_load(f)
        
        if custom_data:
            # Core step: recursively merge dictionaries
            def update_config(base, update):
                for key, value in update.items():
                    if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                        update_config(base[key], value)
                    else:
                        base[key] = value
            
            update_config(config, custom_data)
        else:
            print(f"[Config Warning] File {custom_path} is empty, skipping loading.")

    except Exception as e:
        sys.exit(f"\n[Config Error] Failed to parse YAML file: {e}\n")