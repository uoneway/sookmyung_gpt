from itertools import chain, combinations, zip_longest


def chunk_list(input_list, chunk_size):
    if chunk_size is None:
        yield input_list
    else:
        for i in range(0, len(input_list), chunk_size):
            yield input_list[i : i + chunk_size]


def pick_idxs_by_rank(idxs_from_ss: list, idxs_from_ks: list, num_by_each_rank: int, num_by_mixed_rank: int):
    """두 기준의 결과 순서를 답은 두 idx를 합친 idx list를 반환하는 함수
    1. 각 그룹 내 순위만 고려하여 num_by_each_rank 만큼 뽑는다. 이를 우선적으로 상위에 둠
        - 앞 그룹이 우선적으로 고려됨
        - 중복이 당연히 있을 수 있으니 그 차순위를 고려함
    2. 두 그룹 내 순위를 혼합적으로 고려하여 num_by_mixed_rank만큼 뽑음

    merge_idxs([3,10,7,8,6,5], [10,6,5,2])
    score: {3: 7, 10: 1, 7: 9, 8: 10, 6: 5, 5: 7, 2: 10}
    result: [3, 10, 6, 7, 5, 8, 2]
    """
    # 각 그룹 내에서의 순위만 고려
    merge_idxs = alternate_merge(idxs_from_ss, idxs_from_ks)
    idxs_by_each_rank = remove_duplicates(merge_idxs)

    idxs_pick = idxs_by_each_rank[:num_by_each_rank]

    # 두 그룹 내 rank를 혼합적으로 고려
    # 각 인덱스에 대해 순위를 계산하고 합산
    rank_dict = {}
    for i in range(len(idxs_from_ss)):
        if idxs_from_ss[i] in rank_dict:
            rank_dict[idxs_from_ss[i]] += i
        else:
            rank_dict[idxs_from_ss[i]] = i
    for i in range(len(idxs_from_ks)):
        if idxs_from_ks[i] in rank_dict:
            rank_dict[idxs_from_ks[i]] += i
        else:
            rank_dict[idxs_from_ks[i]] = i

    # 한 리스트에만 있는 인덱스에 대해 패널티 부여
    max_len = max(len(idxs_from_ss), len(idxs_from_ks))
    for idx, rank_sum in rank_dict.items():
        if idxs_from_ss.count(idx) == 0 or idxs_from_ks.count(idx) == 0:
            rank_dict[idx] = rank_sum + max_len + 1

    # print(rank_dict)
    # 순위 합이 가장 낮은 상위 L개의 인덱스를 선택
    # 동점인 경우는 무시
    idxs_by_mixed_rank = sorted(rank_dict.items(), key=lambda x: x[1])

    for idx, mix_rank in idxs_by_mixed_rank:
        if idx not in idxs_pick:
            idxs_pick.append(idx)
            if len(idxs_pick) == num_by_each_rank + num_by_mixed_rank:
                break
    return idxs_pick


def remove_duplicates(lst):
    # 리스트의 순서를 유지하면서 중복을 제거
    seen = set()
    new_list = [x for x in lst if not (x in seen or seen.add(x))]
    return new_list


def alternate_merge(list1, list2):
    # 두 리스트를 번갈아 가면서 값을 추출하여 새로운 리스트를 만듦
    return [item for item in chain(*zip_longest(list1, list2)) if item is not None]


def get_dict_value_by_keys(d: dict, keys: str | list[str], default=None):
    if isinstance(keys, str):
        keys = [keys]

    for key in keys[:-1]:
        d = d.get(key, {})
    return d.get(keys[-1], default)


def powerset(iterable):
    "powerset([1,2,3]) --> () (1,) (2,) (3,) (1,2) (1,3) (2,3) (1,2,3)"
    s = list(iterable)  # allows duplicate elements
    return chain.from_iterable(combinations(s, r) for r in range(len(s) + 1))


def get_sequential_combinations(x: list[str]):
    return [x[i:j] for i, j in combinations(range(len(x) + 1), 2)]
