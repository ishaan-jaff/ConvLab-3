import json
import os
from convlab2.util import load_dataset, load_dst_data
from convlab2.base_models.t5.dst.serialization import deserialize_state


def merge(dataset_name, speaker, save_dir, context_window_size, predict_result):
    assert os.path.exists(predict_result)
    dataset = load_dataset(dataset_name)
    data = load_dst_data(dataset, data_split='test', speaker=speaker, use_context=context_window_size>0, context_window_size=context_window_size)['test']
    
    if save_dir is None:
        save_dir = os.path.dirname(predict_result)
    else:
        os.makedirs(save_dir, exist_ok=True)
    predict_result = [deserialize_state(json.loads(x)['predictions'].strip()) for x in open(predict_result)]

    for sample, prediction in zip(data, predict_result):
        sample['predictions'] = {'state': prediction}

    json.dump(data, open(os.path.join(save_dir, 'predictions.json'), 'w', encoding='utf-8'), indent=2, ensure_ascii=False)


if __name__ == '__main__':
    from argparse import ArgumentParser
    parser = ArgumentParser(description="merge predict results with original data for unified NLU evaluation")
    parser.add_argument('--dataset', '-d', metavar='dataset_name', type=str, help='name of the unified dataset')
    parser.add_argument('--speaker', '-s', type=str, choices=['user', 'system', 'all'], help='speaker(s) of utterances')
    parser.add_argument('--save_dir', type=str, help='merged data will be saved as $save_dir/predictions.json. default: on the same directory as predict_result')
    parser.add_argument('--context_window_size', '-c', type=int, default=0, help='how many contextual utterances are considered')
    parser.add_argument('--predict_result', '-p', type=str, required=True, help='path to the output file generated_predictions.json')
    args = parser.parse_args()
    print(args)
    merge(args.dataset, args.speaker, args.save_dir, args.context_window_size, args.predict_result)
