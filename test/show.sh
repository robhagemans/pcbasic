test=$1
cd "$test/model"

for file in *
do
    echo
    echo "$file --------------------------------------------------------------------------"
    colordiff "$file" "../output/$file"
done
