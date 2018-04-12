test=$1
SCRIPTDIR="$(dirname -- "$0")"
cd "$SCRIPTDIR/$test/model"

for file in *
do
    echo
    echo "$file --------------------------------------------------------------------------"
    colordiff "../output/$file" "$file"
done
