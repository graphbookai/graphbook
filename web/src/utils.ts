export const keyRecursively = (obj: Array<any>, childrenKey: string = "children"): Array<any> => {
    let currKeyVal = 0;
    const keyRec = (obj: Array<any>) => {
        return obj.map((item) => {
            if (item[childrenKey]) {
                return {
                    ...item,
                    key: currKeyVal++,
                    [childrenKey]: keyRec(item[childrenKey])
                }
            }
            return {
                ...item,
                key: currKeyVal++
            };
        });
    }

    return keyRec(obj);
}

export const mediaUrl = (url: string) : string => {
    return `http://localhost:8006/${url}`; // TODO: change in settings
}
