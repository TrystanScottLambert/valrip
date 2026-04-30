"""
Module for handling yaml loading and dumping.
"""

from yaml import SafeDumper, SafeLoader

SafeDumper.add_representer(
    type(None),
    lambda dumper, _: dumper.represent_scalar("tag:yaml.org,2002:null", ""),
)


class NoDatesSafeLoader(SafeLoader):
    """Overrides pyyaml's interpretation of some strings as dates so we can
    keep YYYY-MM-DD as plain strings (downstream code serialises to JSON,
    which has no date type). See https://stackoverflow.com/a/37958106."""

    @classmethod
    def remove_implicit_resolver(cls, tag_to_remove):
        if "yaml_implicit_resolvers" not in cls.__dict__:
            cls.yaml_implicit_resolvers = cls.yaml_implicit_resolvers.copy()

        for first_letter, mappings in cls.yaml_implicit_resolvers.items():
            cls.yaml_implicit_resolvers[first_letter] = [
                (tag, regexp) for tag, regexp in mappings if tag != tag_to_remove
            ]


NoDatesSafeLoader.remove_implicit_resolver("tag:yaml.org,2002:timestamp")
