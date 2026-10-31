import React from 'react';
import {Composition} from 'remotion';
import {Reel} from './Reel';
import {ReelProps} from './types';
import sample from './sample-props.json';

export const Root: React.FC = () => (
  <Composition
    id="Reel"
    component={Reel as any}
    width={1080}
    height={1920}
    fps={30}
    durationInFrames={300}
    defaultProps={sample as unknown as ReelProps}
    calculateMetadata={async ({props}) => ({durationInFrames: (props as ReelProps).durationFrames})}
  />
);
